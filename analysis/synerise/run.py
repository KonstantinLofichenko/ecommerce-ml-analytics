"""Bounded-memory research over original Synerise Parquet; no production database access."""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from string import Template

import duckdb

EVENTS = ("product_buy", "add_to_cart", "remove_from_cart", "page_visit", "search_query")
SQL = Path(__file__).with_name("sql")


def query(connection, sql):
    cursor = connection.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def setup(connection, source):
    for name in (*EVENTS, "product_properties"):
        path = str(source / f"{name}.parquet").replace("'", "''")
        connection.execute(
            f"CREATE OR REPLACE TEMP VIEW raw_{name} AS SELECT * FROM read_parquet('{path}')"
        )
        if name in EVENTS:
            connection.execute(f"""CREATE OR REPLACE TEMP VIEW {name} AS SELECT *,
                TRY_CAST(timestamp AS TIMESTAMP) AS ts FROM raw_{name}""")
        else:
            connection.execute(
                "CREATE OR REPLACE TEMP VIEW properties AS SELECT * FROM raw_product_properties"
            )
    parts = [
        f"SELECT '{name}' AS kind,client_id,ts,"
        + ("sku" if name in EVENTS[:3] else "NULL::BIGINT")
        + " AS sku FROM "
        + name
        for name in EVENTS
    ]
    connection.execute("CREATE OR REPLACE TEMP VIEW events AS " + " UNION ALL ".join(parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/external/synerise/source"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("analysis/synerise/results.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "source": str(args.source),
        "duckdb": duckdb.__version__,
        "memory_limit": "2GB",
        "threads": 2,
        "executions": [],
    }
    if args.resume and args.output.exists():
        result = json.loads(args.output.read_text())
    start = time.monotonic()
    with (
        tempfile.TemporaryDirectory(prefix="synerise-spill-") as spill,
        duckdb.connect(str(Path(spill) / "scratch.duckdb")) as c,
    ):
        c.execute("SET memory_limit='2GB'")
        c.execute("SET threads=2")
        c.execute("SET preserve_insertion_order=false")
        c.execute("SET max_temp_directory_size='80GB'")
        c.execute("SET temp_directory=?", [spill])
        setup(c, args.source.resolve())

        def execute(name, sql):
            if args.resume and any(
                e["name"] == name and e["sql"] == sql for e in result["executions"]
            ):
                print(f"Reusing completed {name}", flush=True)
                return result[name]
            begun = time.monotonic()
            print(f"Starting {name}", flush=True)
            rows = query(c, sql)
            result[name] = rows
            result["executions"].append(
                {
                    "name": name,
                    "seconds": time.monotonic() - begun,
                    "sql": sql,
                    "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                    "status": "executed",
                }
            )
            args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
            print(f"Completed {name}: {time.monotonic() - begun:.2f}s", flush=True)
            return rows

        for name in (*EVENTS, "product_properties"):
            columns = execute(f"{name}_schema", f"DESCRIBE raw_{name}")
            names = [r["column_name"] for r in columns]
            nulls = ",".join(f'count_if("{col}" IS NULL) AS "{col}_nulls"' for col in names)
            execute(f"{name}_nulls", f"SELECT count(*) AS rows,{nulls} FROM raw_{name}")
            if name in EVENTS:
                item = "sku" if name in EVENTS[:3] else ("url" if name == "page_visit" else None)
                distinct = f", count(DISTINCT {item}) AS distinct_values" if item else ""
                execute(
                    f"{name}_profile",
                    f"""SELECT count(*) AS events,
                    count(DISTINCT client_id) AS clients,
                    approx_count_distinct(client_id) AS approx_clients,
                    count_if(client_id<=0) AS nonpositive_clients,
                    min(ts) AS first_ts,max(ts) AS last_ts,
                    count_if(timestamp IS NOT NULL AND ts IS NULL) AS invalid_timestamps,
                    count_if(ts!=date_trunc('second',ts)) AS fractional_timestamps {distinct}
                    FROM {name}""",
                )
                execute(
                    f"{name}_daily",
                    f"""SELECT CAST(ts AS DATE) AS date,count(*) AS events,
                    count(DISTINCT client_id) AS clients FROM {name} GROUP BY date ORDER BY date""",
                )
                execute(
                    f"{name}_monthly",
                    f"""SELECT date_trunc('month',ts) AS month,
                    count(*) AS events,count(DISTINCT client_id) AS clients
                    FROM {name} GROUP BY month ORDER BY month""",
                )
            keys = ",".join('"' + col + '"' for col in names)
            template = (
                f"SELECT count(*) AS distinct_rows,sum(n-1) AS excess_rows,"
                f"count_if(n>1) AS duplicate_groups,max(n) AS max_multiplicity "
                f"FROM (SELECT count(*) AS n FROM raw_{name} $filter GROUP BY {keys})"
            )
            if name == "page_visit":
                partitions = [
                    execute(
                        f"{name}_duplicates_part_{i}",
                        template.replace("$filter", f"WHERE hash(client_id)%32={i}"),
                    )[0]
                    for i in range(32)
                ]
                result[f"{name}_duplicates"] = [
                    {
                        key: (max if key == "max_multiplicity" else sum)(
                            row[key] for row in partitions
                        )
                        for key in partitions[0]
                    }
                ]
            else:
                execute(f"{name}_duplicates", template.replace("$filter", ""))
        execute(
            "product_metadata",
            """SELECT count(*) AS rows,count(DISTINCT sku) AS skus,
            count(*)-count(DISTINCT sku) AS excess_sku_keys,
            count(DISTINCT category) AS categories,min(price) AS minimum_price_bucket,
            max(price) AS maximum_price_bucket FROM properties""",
        )
        for name in EVENTS[:3]:
            execute(
                f"{name}_property_coverage",
                f"""SELECT count(*) AS events,
                count_if(p.sku IS NULL) AS unmatched_events,
                count(DISTINCT e.sku) FILTER (WHERE p.sku IS NULL) AS unmatched_skus
                FROM {name} e LEFT JOIN (SELECT DISTINCT sku FROM properties) p USING(sku)""",
            )
        execute(
            "embedding_lengths",
            """SELECT 'query' AS field,len(regexp_extract_all(query,'[0-9]+')) AS dimensions,
            count(*) AS rows
            FROM search_query GROUP BY len(regexp_extract_all(query,'[0-9]+'))
            UNION ALL SELECT 'name',len(regexp_extract_all(name,'[0-9]+')),count(*)
            FROM properties GROUP BY len(regexp_extract_all(name,'[0-9]+'))""",
        )
        begun = time.monotonic()
        for i in range(32):
            print(f"Aggregating customer partition {i + 1}/32", flush=True)
            statement = f"""SELECT client_id,count(*) AS n,
            count(DISTINCT CAST(ts AS DATE)) AS days,
            count(DISTINCT date_trunc('month',ts)) AS months,
            count_if(kind='product_buy') AS buys,
            count(DISTINCT CAST(ts AS DATE)) FILTER (WHERE kind='product_buy') AS buy_days,
            min(ts) AS first_ts,max(ts) AS last_ts,
            bool_or(kind='page_visit') AS page,bool_or(kind='search_query') AS search,
            bool_or(kind='add_to_cart') AS cart
            FROM events WHERE client_id IS NOT NULL AND hash(client_id)%32={i} GROUP BY client_id"""
            c.execute(
                (
                    "CREATE TEMP TABLE customer_activity AS "
                    if i == 0
                    else "INSERT INTO customer_activity "
                )
                + statement
            )
        result["customer_aggregation_seconds"] = time.monotonic() - begun
        c.execute("""CREATE TEMP TABLE snapshots AS
            SELECT snapshot FROM (
              SELECT unnest(generate_series(date_trunc('month',min(ts))+INTERVAL 2 MONTH,
                date_trunc('month',max(ts)),INTERVAL 1 MONTH)) AS snapshot FROM events
            ) WHERE snapshot+INTERVAL 14 DAY <= (SELECT max(ts) FROM events)
            ORDER BY snapshot DESC LIMIT 4""")
        for name in (
            "customer_history",
            "purchases",
            "purchase_ties",
            "snapshots",
            "customer_funnel",
        ):
            execute(name, (SQL / f"{name}.sql").read_text())
        execute(
            "repeat_products",
            """SELECT
            (SELECT count(*) FROM (SELECT client_id,sku FROM product_buy
              GROUP BY client_id,sku HAVING count(DISTINCT ts)>1)) AS repeat_client_sku_pairs,
            (SELECT count(*) FROM (SELECT client_id,category FROM product_buy b
              JOIN (SELECT DISTINCT sku,category FROM properties) p USING(sku)
              GROUP BY client_id,category HAVING count(DISTINCT ts)>1))
              AS repeat_client_category_pairs""",
        )
        for i in range(16):
            for event in EVENTS:
                c.execute(
                    f"CREATE OR REPLACE TEMP VIEW {event} AS SELECT *, "
                    f"TRY_CAST(timestamp AS TIMESTAMP) AS ts FROM raw_{event} "
                    f"WHERE hash(client_id)%16={i}"
                )
            for days in (-1, 1, 7, 30):
                execute(
                    f"funnel_{days}_part_{i}",
                    Template((SQL / "bounded_funnel.sql").read_text()).substitute(days=days),
                )
        for days in (-1, 1, 7, 30):
            parts = [result[f"funnel_{days}_part_{i}"][0] for i in range(16)]
            result[f"funnel_{days}"] = [
                {
                    key: days if key == "window_days" else sum(p[key] for p in parts)
                    for key in parts[0]
                }
            ]
        result["duration_seconds"] = time.monotonic() - start
        args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
