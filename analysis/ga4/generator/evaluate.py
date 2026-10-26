"""Assess local ec_demo output without touching project databases or training models."""

import argparse
import json
import tempfile
from pathlib import Path

import duckdb


def records(connection, sql):
    cursor = connection.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def snapshot_counts(connection):
    """Use observed event purchases, strict prior eligibility, half-open outcomes."""
    return records(
        connection,
        """
        WITH snapshots AS (
          SELECT unnest([TIMESTAMP '2025-02-01', TIMESTAMP '2025-02-15',
            TIMESTAMP '2025-03-01', TIMESTAMP '2025-03-15']) AS snapshot
        ), identities AS (
          SELECT 'pseudo_id' AS identity, pseudo AS customer, ts FROM events
            WHERE name = 'purchase' AND pseudo IS NOT NULL
          UNION ALL SELECT 'observed_login_id', uid, ts FROM events
            WHERE name = 'purchase' AND uid IS NOT NULL
          UNION ALL SELECT 'order_customer_id', customer_id, ts FROM orders
            WHERE customer_id IS NOT NULL
        ), labels AS (
          SELECT identity, snapshot, customer,
            count_if(ts < snapshot) AS prior_purchases,
            count_if(ts >= snapshot AND ts < snapshot + INTERVAL 14 DAY) > 0 AS positive
          FROM identities CROSS JOIN snapshots GROUP BY ALL
          HAVING count_if(ts < snapshot) > 0
        )
        SELECT identity, snapshot, count(*) AS eligible, count_if(positive) AS positives,
          count_if(NOT positive) AS negatives, avg(positive::INT) AS positive_rate,
          min(prior_purchases) AS minimum_prior_purchases
        FROM labels GROUP BY ALL ORDER BY identity, snapshot
    """,
    )


def evaluate(directory):
    connection = duckdb.connect()
    connection.execute("SET memory_limit = '1GB'")
    connection.execute("SET threads = 2")
    files = sorted(directory.glob("events_*.jsonl"))
    if not files:
        raise ValueError("No daily event files found")
    with tempfile.TemporaryDirectory(prefix="ec-demo-audit-") as temporary:
        compact = Path(temporary) / "events.jsonl"
        with compact.open("w") as output:
            for file in files:
                with file.open() as source:
                    for line in source:
                        event = json.loads(line)
                        parameters = event["event_params"]
                        sessions = [
                            p["value"].get("int_value")
                            for p in parameters
                            if p["key"] == "ga_session_id"
                        ]
                        output.write(
                            json.dumps(
                                {
                                    "name": event["event_name"],
                                    "micros": event["event_timestamp"],
                                    "pseudo": event.get("user_pseudo_id"),
                                    "uid": event.get("user_id"),
                                    "sid": sessions[0] if len(sessions) == 1 else None,
                                    "tx": (event.get("ecommerce") or {}).get("transaction_id"),
                                    "first_touch": event.get("user_first_touch_timestamp"),
                                }
                            )
                            + "\n"
                        )
        connection.execute(
            """
          CREATE TEMP TABLE events AS SELECT *,
            make_timestamp(micros::BIGINT) AS ts
          FROM read_json_auto(?)
        """,
            [str(compact)],
        )
        connection.execute(
            """
          CREATE TEMP TABLE orders AS SELECT *,
            CAST(order_datetime AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS ts
          FROM read_csv(?, header=true, all_varchar=true)
        """,
            [str(directory / "orders.csv")],
        )
        result = {
            "event_files": len(files),
            "output_bytes": sum(f.stat().st_size for f in directory.iterdir() if f.is_file()),
        }
        result["events"] = records(
            connection,
            """
          SELECT count(*) AS events, count(DISTINCT pseudo) AS pseudo_ids,
            count(DISTINCT uid) AS login_ids, min(ts) AS first_utc, max(ts) AS last_utc,
            count_if(uid IS NULL) AS null_login_events,
            count_if(pseudo IS NULL) AS null_pseudo_events,
            count_if(sid IS NULL) AS null_session_events FROM events
        """,
        )[0]
        result["event_names"] = records(
            connection, "SELECT name, count(*) AS events FROM events GROUP BY name ORDER BY name"
        )
        result["purchase_quality"] = records(
            connection,
            """
          SELECT count(*) AS purchase_events, count(DISTINCT tx) AS transactions,
            count_if(tx IS NULL) AS missing_transactions,
            count(DISTINCT pseudo) AS purchasing_pseudo_ids,
            count(DISTINCT uid) AS purchasing_login_ids,
            count_if(uid IS NULL) AS missing_login_purchases,
            (SELECT count(*) FROM orders) AS orders,
            (SELECT count(DISTINCT order_id) FROM orders) AS unique_orders,
            (SELECT count(DISTINCT customer_id) FROM orders) AS ordering_customers,
            (SELECT count(*) FROM orders o WHERE NOT EXISTS
              (SELECT 1 FROM events e WHERE e.name='purchase' AND e.tx=o.order_id))
              AS orders_without_purchase_event
          FROM events WHERE name='purchase'
        """,
        )[0]
        result["history"] = records(
            connection,
            """
          WITH people AS (
            SELECT pseudo, count_if(name='purchase') AS purchases,
              date_diff('day', min(ts), max(ts)) AS observed_span_days
            FROM events GROUP BY pseudo
          ), gaps AS (
            SELECT (epoch(ts) - epoch(lag(ts) OVER
              (PARTITION BY pseudo ORDER BY ts))) / 86400 AS days
            FROM events WHERE name='purchase'
          )
          SELECT (SELECT count_if(purchases>=2) FROM people) AS repeat_pseudo_ids,
            (SELECT median(observed_span_days) FROM people) AS median_observed_span_days,
            (SELECT count_if(observed_span_days>=60) FROM people) AS pseudo_ids_with_60d_span,
            count(days) AS purchase_gaps, min(days) AS min_gap_days,
            median(days) AS median_gap_days, quantile_cont(days,0.9) AS p90_gap_days
          FROM gaps
        """,
        )[0]
        result["identity_quality"] = records(
            connection,
            """
          WITH links AS (SELECT pseudo, count(DISTINCT uid) AS users,
            count(DISTINCT first_touch) AS first_touches FROM events GROUP BY pseudo)
          SELECT count_if(users>1) AS pseudo_ids_with_multiple_login_ids,
            count_if(first_touches>1) AS pseudo_ids_with_changing_first_touch,
            (SELECT count(*)-count(DISTINCT customer_id)
              FROM read_csv(?,header=true,all_varchar=true)) AS duplicate_customer_master_ids
          FROM links
        """.replace("?", "'" + str(directory / "customers.csv").replace("'", "''") + "'"),
        )[0]
        result["repeat_by_identity"] = records(
            connection,
            """
          WITH source AS (
            SELECT 'observed_login_id' AS identity, uid AS customer, ts FROM events
              WHERE name='purchase' AND uid IS NOT NULL
            UNION ALL SELECT 'order_customer_id', customer_id, ts FROM orders
              WHERE customer_id IS NOT NULL
          ), frequencies AS (
            SELECT identity, customer, count(*) AS purchases,
              date_diff('day', min(ts), max(ts)) AS purchase_span_days
            FROM source GROUP BY ALL
          ), gaps AS (
            SELECT identity, (epoch(ts)-epoch(lag(ts) OVER
              (PARTITION BY identity, customer ORDER BY ts)))/86400 AS days FROM source
          )
          SELECT f.identity, count(*) AS purchasing_customers,
            count_if(purchases>=2) AS repeat_customers,
            median(purchases) AS median_purchases_per_customer,
            median(purchase_span_days) AS median_purchase_span_days,
            (SELECT median(days) FROM gaps g WHERE g.identity=f.identity) AS median_gap_days
          FROM frequencies f GROUP BY f.identity ORDER BY f.identity
        """,
        )
        result["snapshots"] = snapshot_counts(connection)
        result["funnel"] = records(
            connection,
            """
          WITH stages AS (
            SELECT pseudo,sid,min(ts) FILTER (WHERE name='page_view') AS t1,
              bool_or(name='page_view') AS p1, bool_or(name='view_item') AS p2,
              bool_or(name='add_to_cart') AS p3, bool_or(name='begin_checkout') AS p4,
              bool_or(name='purchase') AS p5 FROM events
            WHERE pseudo IS NOT NULL AND sid IS NOT NULL GROUP BY ALL
          ), s2 AS (
            SELECT s.*,min(e.ts) AS t2 FROM stages s LEFT JOIN events e
              ON e.pseudo=s.pseudo AND e.sid=s.sid AND e.name='view_item' AND e.ts>s.t1
            GROUP BY ALL
          ), s3 AS (
            SELECT s.*,min(e.ts) AS t3 FROM s2 s LEFT JOIN events e
              ON e.pseudo=s.pseudo AND e.sid=s.sid AND e.name='add_to_cart' AND e.ts>s.t2
            GROUP BY ALL
          ), s4 AS (
            SELECT s.*,min(e.ts) AS t4 FROM s3 s LEFT JOIN events e
              ON e.pseudo=s.pseudo AND e.sid=s.sid AND e.name='begin_checkout' AND e.ts>s.t3
            GROUP BY ALL
          ), s5 AS (
            SELECT s.*,min(e.ts) AS t5 FROM s4 s LEFT JOIN events e
              ON e.pseudo=s.pseudo AND e.sid=s.sid AND e.name='purchase' AND e.ts>s.t4
            GROUP BY ALL
          )
          SELECT count(*) AS sessions, count_if(p1) AS presence_page,
            count_if(p1 AND p2) AS presence_item,
            count_if(p1 AND p2 AND p3) AS presence_cart,
            count_if(p1 AND p2 AND p3 AND p4) AS presence_checkout,
            count_if(p1 AND p2 AND p3 AND p4 AND p5) AS presence_purchase,
            count(t1) AS strict_page, count(t2) AS strict_item, count(t3) AS strict_cart,
            count(t4) AS strict_checkout, count(t5) AS strict_purchase FROM s5
        """,
        )[0]
    connection.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.input.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(f"Aggregate assessment written to {args.output}")


if __name__ == "__main__":
    main()
