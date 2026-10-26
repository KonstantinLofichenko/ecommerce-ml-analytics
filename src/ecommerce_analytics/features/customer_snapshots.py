"""Leakage-safe prior-purchaser snapshots, computed entirely from raw event times."""

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import pandas as pd

from ecommerce_analytics.analytics.exploration import ExplorationError

DEFAULT_SNAPSHOTS = (date(2019, 11, 1), date(2019, 12, 1), date(2020, 1, 1), date(2020, 2, 1))
EXPECTED_COUNTS = {
    date(2019, 11, 1): (25762, 2373),
    date(2019, 12, 1): (52523, 3382),
    date(2020, 1, 1): (72225, 3699),
    date(2020, 2, 1): (92652, 4380),
}
FEATURES = {
    "days_since_last_purchase": "Elapsed fractional UTC days since latest prior purchase.",
    "purchase_sessions_30d": "Distinct known customer/session pairs with a purchase in [t−30d, t).",
    "sessions_30d": "Distinct known customer/session pairs with any event in [t−30d, t).",
    "view_events_30d": "Raw view-event count in [t−30d, t).",
    "cart_events_30d": "Raw cart-event count in [t−30d, t).",
    "remove_events_30d": "Raw remove_from_cart-event count in [t−30d, t).",
    "purchase_events_30d": "Raw purchase-event count in [t−30d, t).",
    "distinct_products_30d": "Distinct nonmissing products across all events in [t−30d, t).",
    "days_since_last_event": "Elapsed fractional UTC days since latest prior event.",
    "historical_purchasing_sessions": "Distinct known purchasing customer/session pairs before t.",
}
COUNT_FEATURES = tuple(name for name in FEATURES if not name.startswith("days_since"))


def _historical_features(con: duckdb.DuckDBPyConnection, snapshot: date) -> None:
    """No event at or after t is accessible to this feature aggregation."""
    con.execute(
        "CREATE OR REPLACE TEMP TABLE snapshot_parameters AS SELECT ?::TIMESTAMP AS t",
        [datetime.combine(snapshot, time())],
    )
    con.execute("""
        CREATE OR REPLACE TEMP TABLE eligible_purchasers AS
        SELECT user_id, max(event_time_utc) AS last_purchase_utc,
          count(DISTINCT struct_pack(user_id := user_id, user_session := user_session))
            FILTER (WHERE user_session IS NOT NULL) AS historical_purchasing_sessions
        FROM raw_events CROSS JOIN snapshot_parameters
        WHERE user_id IS NOT NULL AND event_type = 'purchase' AND event_time_utc < t
        GROUP BY user_id
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE snapshot_history AS
        WITH past AS (
            SELECT r.*, p.t, r.event_time_utc >= p.t - INTERVAL '30 days' AS recent
            FROM raw_events r JOIN eligible_purchasers e USING (user_id)
            CROSS JOIN snapshot_parameters p WHERE r.event_time_utc < p.t
        ) SELECT user_id,
          count(DISTINCT struct_pack(user_id := user_id, user_session := user_session))
            FILTER (WHERE recent AND user_session IS NOT NULL AND event_type = 'purchase')
            AS purchase_sessions_30d,
          count(DISTINCT struct_pack(user_id := user_id, user_session := user_session))
            FILTER (WHERE recent AND user_session IS NOT NULL) AS sessions_30d,
          count(*) FILTER (WHERE recent AND event_type = 'view') AS view_events_30d,
          count(*) FILTER (WHERE recent AND event_type = 'cart') AS cart_events_30d,
          count(*) FILTER (WHERE recent AND event_type = 'remove_from_cart') AS remove_events_30d,
          count(*) FILTER (WHERE recent AND event_type = 'purchase') AS purchase_events_30d,
          count(DISTINCT product_id) FILTER (WHERE recent) AS distinct_products_30d,
          max(event_time_utc) AS last_event_utc,
          min(event_time_utc) FILTER (WHERE recent) AS first_recent_event_utc,
          max(event_time_utc) FILTER (WHERE recent) AS last_recent_event_utc,
          count(*) FILTER (WHERE user_session IS NULL) AS past_events_missing_session
        FROM past GROUP BY user_id
    """)


def _future_labels(con: duckdb.DuckDBPyConnection) -> None:
    """Future events are accessible only to label construction and label audits."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE snapshot_labels AS
        SELECT r.user_id, count(*) AS label_purchase_events,
          min(event_time_utc) AS first_label_purchase_utc,
          max(event_time_utc) AS last_label_purchase_utc
        FROM raw_events r JOIN eligible_purchasers e USING (user_id)
        CROSS JOIN snapshot_parameters p
        WHERE r.event_type = 'purchase' AND r.event_time_utc >= p.t
          AND r.event_time_utc < p.t + INTERVAL '14 days'
        GROUP BY r.user_id
    """)


def _append_snapshot(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        INSERT INTO customer_snapshot_features
        SELECT p.t::DATE AS prediction_date, e.user_id,
          (l.user_id IS NOT NULL)::TINYINT AS target_14d,
          epoch(p.t - e.last_purchase_utc) / 86400.0 AS days_since_last_purchase,
          h.purchase_sessions_30d, h.sessions_30d, h.view_events_30d, h.cart_events_30d,
          h.remove_events_30d, h.purchase_events_30d, h.distinct_products_30d,
          epoch(p.t - h.last_event_utc) / 86400.0 AS days_since_last_event,
          e.historical_purchasing_sessions
        FROM eligible_purchasers e JOIN snapshot_history h USING (user_id)
        LEFT JOIN snapshot_labels l USING (user_id) CROSS JOIN snapshot_parameters p
    """)


def _validate_snapshot(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Independently reconcile eligible/positive keys against raw interval queries."""
    audit = con.execute("""
        WITH reference_eligible AS (
            SELECT DISTINCT r.user_id FROM raw_events r CROSS JOIN snapshot_parameters p
            WHERE r.user_id IS NOT NULL AND r.event_type = 'purchase' AND r.event_time_utc < p.t
        ), reference_positive AS (
            SELECT DISTINCT r.user_id FROM raw_events r
            JOIN reference_eligible e USING (user_id) CROSS JOIN snapshot_parameters p
            WHERE r.event_type = 'purchase' AND r.event_time_utc >= p.t
              AND r.event_time_utc < p.t + INTERVAL '14 days'
        ), actual AS (
            SELECT f.* FROM customer_snapshot_features f CROSS JOIN snapshot_parameters p
            WHERE f.prediction_date = p.t::DATE
        ), eligibility_difference AS (
            (SELECT user_id FROM actual EXCEPT SELECT user_id FROM reference_eligible)
            UNION ALL
            (SELECT user_id FROM reference_eligible EXCEPT SELECT user_id FROM actual)
        ), positive_difference AS (
            (SELECT user_id FROM actual WHERE target_14d = 1
                EXCEPT SELECT user_id FROM reference_positive)
            UNION ALL
            (SELECT user_id FROM reference_positive
                EXCEPT SELECT user_id FROM actual WHERE target_14d = 1)
        ) SELECT p.t::DATE AS prediction_date,
          (SELECT count(*) FROM eligibility_difference) AS eligibility_key_errors,
          (SELECT count(*) FROM positive_difference) AS label_key_errors,
          (SELECT count(*) - count(DISTINCT user_id) FROM actual) AS duplicate_key_errors,
          (SELECT count(*) FROM snapshot_history WHERE last_event_utc >= p.t
             OR first_recent_event_utc < p.t - INTERVAL '30 days'
             OR last_recent_event_utc >= p.t) AS feature_time_errors,
          (SELECT count(*) FROM eligible_purchasers WHERE last_purchase_utc >= p.t
             OR last_purchase_utc IS NULL) AS prior_purchase_errors,
          (SELECT count(*) FROM snapshot_labels WHERE first_label_purchase_utc < p.t
             OR last_label_purchase_utc >= p.t + INTERVAL '14 days') AS label_time_errors,
          (SELECT max(last_event_utc) FROM snapshot_history) AS latest_feature_event_utc,
          (SELECT min(first_recent_event_utc) FROM snapshot_history) AS earliest_30d_event_utc,
          (SELECT min(first_label_purchase_utc) FROM snapshot_labels) AS first_label_purchase_utc,
          (SELECT max(last_label_purchase_utc) FROM snapshot_labels) AS last_label_purchase_utc,
          (SELECT coalesce(sum(past_events_missing_session), 0) FROM snapshot_history)
            AS historical_events_missing_session
        FROM snapshot_parameters p
    """).df()
    if audit[[column for column in audit if column.endswith("_errors")]].to_numpy().any():
        raise ExplorationError("Snapshot failed eligibility, key, or timestamp validation.")
    return audit


def summarize_features(
    con: duckdb.DuckDBPyConnection, expected: Mapping[date, tuple[int, int]]
) -> dict[str, pd.DataFrame]:
    summary = con.execute("""
        SELECT a.prediction_date, count(f.user_id) AS eligible_customers,
          count(*) FILTER (WHERE target_14d = 1) AS positive_labels,
          count(*) FILTER (WHERE target_14d = 0) AS negative_labels,
          avg(target_14d) AS positive_rate
        FROM customer_snapshot_build_audit a LEFT JOIN customer_snapshot_features f
          USING (prediction_date) GROUP BY a.prediction_date ORDER BY a.prediction_date
    """).df()
    summary["expected_eligible"] = [
        expected.get(d.date(), (None, None))[0] for d in summary.prediction_date
    ]
    summary["expected_positive"] = [
        expected.get(d.date(), (None, None))[1] for d in summary.prediction_date
    ]
    summary["eligible_difference"] = summary.eligible_customers - summary.expected_eligible
    summary["positive_difference"] = summary.positive_labels - summary.expected_positive
    summary["reconciliation"] = [
        "not provided"
        if row.expected_eligible is None or pd.isna(row.expected_eligible)
        else (
            "match"
            if row.eligible_difference == 0 and row.positive_difference == 0
            else "DISCREPANCY: inspect source coverage and snapshot definitions"
        )
        for row in summary.itertuples()
    ]
    statistics = []
    for feature in FEATURES:
        statistics.append(
            con.execute(f"""
            SELECT prediction_date, '{feature}' AS feature, count(*) AS rows,
              count(*) FILTER (WHERE {feature} IS NULL) AS nulls,
              min({feature}) AS minimum, avg({feature}) AS mean,
              quantile_cont({feature}, .5) AS median, quantile_cont({feature}, .95) AS p95,
              max({feature}) AS maximum
            FROM customer_snapshot_features GROUP BY prediction_date ORDER BY prediction_date
        """).df()
        )
    nulls = con.execute(
        " UNION ALL ".join(
            f"SELECT '{column}' AS column_name, count(*) FILTER (WHERE {column} IS NULL) AS nulls "
            "FROM customer_snapshot_features"
            for column in ("prediction_date", "user_id", "target_14d", *FEATURES)
        )
    ).df()
    if nulls.nulls.sum():
        raise ExplorationError("Unexpected NULL in customer snapshot keys, target or features.")
    # Diagnostic alternative only: never feeds the target or historical features.
    comparison = con.execute("""
        WITH firsts AS (
            SELECT user_id, user_session, min(event_time_utc) AS first_purchase_utc
            FROM raw_events WHERE event_type = 'purchase' AND user_id IS NOT NULL
              AND user_session IS NOT NULL GROUP BY user_id, user_session
        ), variants AS (
            SELECT f.prediction_date, f.target_14d,
              EXISTS (SELECT 1 FROM firsts s WHERE s.user_id = f.user_id
                AND s.first_purchase_utc >= f.prediction_date
                AND s.first_purchase_utc < f.prediction_date + INTERVAL '14 days')
                AS new_purchasing_session,
              EXISTS (SELECT 1 FROM raw_events r WHERE r.user_id = f.user_id
                AND r.event_type = 'purchase' AND r.user_session IS NOT NULL
                AND r.event_time_utc >= f.prediction_date
                AND r.event_time_utc < f.prediction_date + INTERVAL '14 days')
                AS known_session_future_purchase
            FROM customer_snapshot_features f
        ) SELECT prediction_date,
          count(*) FILTER (WHERE target_14d = 1) AS event_target_positives,
          count(*) FILTER (WHERE new_purchasing_session) AS new_session_positives,
          count(*) FILTER (WHERE target_14d = 1 AND NOT new_purchasing_session)
            AS event_only_positives,
          count(*) FILTER (WHERE known_session_future_purchase) AS known_session_positives
        FROM variants GROUP BY prediction_date ORDER BY prediction_date
    """).df()
    return {
        "snapshot_summary": summary,
        "label_definition_comparison": comparison,
        "null_checks": nulls,
        "feature_statistics": pd.concat(statistics, ignore_index=True),
        "validation": con.execute(
            "SELECT * FROM customer_snapshot_build_audit ORDER BY prediction_date"
        ).df(),
    }


def build_customer_snapshots(
    database: Path,
    prediction_dates: Sequence[date] = DEFAULT_SNAPSHOTS,
    expected: Mapping[date, tuple[int, int]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, pd.DataFrame]:
    """Replace only feature/audit tables, validating before committing the transaction."""
    database = Path(database)
    if not database.is_file():
        raise ExplorationError(f"Existing DuckDB database not found: {database}")
    dates = list(prediction_dates)
    if not dates or any(type(d) is not date for d in dates) or len(set(dates)) != len(dates):
        raise ExplorationError("Prediction dates must be unique UTC calendar dates.")
    dates.sort()
    log = progress or (lambda message: None)
    try:
        with TemporaryDirectory(prefix="ecommerce-features-") as scratch:
            with duckdb.connect(
                str(database),
                config={
                    "memory_limit": "2GB",
                    "threads": 2,
                    "preserve_insertion_order": False,
                    "temp_directory": scratch,
                },
            ) as con:
                con.execute("SET TimeZone = 'UTC'")
                columns = dict(
                    con.execute(
                        "SELECT column_name, data_type FROM "
                        "information_schema.columns WHERE table_schema='main' "
                        "AND table_name='raw_events'"
                    ).fetchall()
                )
                if (
                    not {"user_id", "user_session", "event_type", "product_id", "event_time_utc"}
                    <= (columns.keys())
                    or columns.get("event_time_utc") != "TIMESTAMP"
                ):
                    raise ExplorationError(
                        "raw_events must have the established UTC TIMESTAMP schema."
                    )
                quality = con.execute("""
                    SELECT count(*) AS raw_events, min(event_time_utc) AS first_event_utc,
                      max(event_time_utc) AS last_event_utc,
                      count(*) FILTER (WHERE user_id IS NULL) AS events_missing_customer,
                      count(*) FILTER (WHERE event_time_utc IS NULL) AS events_missing_timestamp,
                      count(*) FILTER (WHERE user_session IS NULL) AS events_missing_session
                    FROM raw_events
                """).df()
                for snapshot in dates:
                    end = pd.Timestamp(snapshot) + pd.Timedelta(days=14)
                    if (
                        pd.isna(quality.iloc[0].last_event_utc)
                        or quality.iloc[0].last_event_utc < end
                    ):
                        raise ExplorationError(
                            f"Insufficient observed follow-up for {snapshot}: "
                            f"need events through {end} UTC."
                        )
                con.execute("BEGIN TRANSACTION")
                try:
                    count_columns = ", ".join(
                        f"{name} BIGINT NOT NULL CHECK ({name} >= 0)"
                        for name in COUNT_FEATURES
                        if name != "historical_purchasing_sessions"
                    )
                    # Explicit insert column order follows the documented feature schema.
                    con.execute(f"""
                        CREATE OR REPLACE TABLE customer_snapshot_features (
                            prediction_date DATE NOT NULL, user_id VARCHAR NOT NULL,
                            target_14d TINYINT NOT NULL CHECK (target_14d IN (0, 1)),
                            days_since_last_purchase DOUBLE NOT NULL
                                CHECK (days_since_last_purchase > 0),
                            {count_columns},
                            days_since_last_event DOUBLE NOT NULL CHECK (days_since_last_event > 0),
                            historical_purchasing_sessions BIGINT NOT NULL
                                CHECK (historical_purchasing_sessions >= purchase_sessions_30d),
                            PRIMARY KEY (prediction_date, user_id),
                            CHECK (sessions_30d >= purchase_sessions_30d),
                            CHECK (purchase_events_30d >= purchase_sessions_30d),
                            CHECK (days_since_last_event <= days_since_last_purchase)
                        )
                    """)
                    for index, snapshot in enumerate(dates):
                        log(f"Building {snapshot}: prior history, then 14-day labels")
                        _historical_features(con, snapshot)
                        _future_labels(con)
                        _append_snapshot(con)
                        audit = _validate_snapshot(con)
                        con.register("current_snapshot_audit", audit)
                        if index == 0:
                            con.execute(
                                "CREATE OR REPLACE TABLE customer_snapshot_build_audit AS "
                                "SELECT * FROM current_snapshot_audit"
                            )
                        else:
                            con.execute(
                                "INSERT INTO customer_snapshot_build_audit "
                                "SELECT * FROM current_snapshot_audit"
                            )
                        con.unregister("current_snapshot_audit")
                    tables = summarize_features(
                        con, EXPECTED_COUNTS if expected is None else expected
                    )
                    tables["source_quality"] = quality
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                con.execute("CHECKPOINT")
                return tables
    except (duckdb.Error, OSError) as exc:
        raise ExplorationError(f"Cannot build customer snapshots: {exc}") from exc
