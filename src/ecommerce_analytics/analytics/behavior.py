"""Phase 1.2: reusable SQL aggregates; source rows never enter Pandas."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import pandas as pd

from ecommerce_analytics.analytics.exploration import (
    ExplorationError,
    load_events,
    quote_identifier,
)
from ecommerce_analytics.analytics.sessions import prepare_sessions


@dataclass(frozen=True)
class BehaviorReport:
    tables: dict[str, pd.DataFrame]
    session_key: str
    source: str


def _query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def _distribution(con: duckdb.DuckDBPyConnection, relation: str, column: str) -> pd.DataFrame:
    """Continuous percentiles; NULL observations excluded, with sample size explicit."""
    return _query(
        con,
        f"""
        SELECT count({column}) AS observations,
            min({column}) AS minimum,
            quantile_cont({column}, .25) AS p25,
            quantile_cont({column}, .5) AS median,
            quantile_cont({column}, .75) AS p75,
            quantile_cont({column}, .9) AS p90,
            quantile_cont({column}, .95) AS p95,
            quantile_cont({column}, .99) AS p99,
            max({column}) AS maximum, avg({column}) AS mean
        FROM {relation}
    """,
    )


def _funnel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _query(
        con,
        """
        WITH counts AS (
            SELECT count(*) AS all_sessions,
              count(*) FILTER (WHERE has_view) AS presence_view,
              count(*) FILTER (WHERE has_view AND has_cart) AS presence_cart,
              count(*) FILTER (WHERE has_view AND has_cart AND has_purchase) AS presence_purchase,
              count(*) FILTER (WHERE first_view IS NOT NULL) AS chronological_view,
              count(strict_cart) AS chronological_cart,
              count(*) FILTER (WHERE strict_complete) AS chronological_purchase,
              count(*) FILTER (WHERE relaxed_complete AND NOT strict_complete)
                AS tie_dependent_complete,
              count(*) FILTER (WHERE relaxed_cart IS NOT NULL AND strict_cart IS NULL)
                AS tie_dependent_cart
            FROM funnel_sessions
        ), stages AS (
            SELECT 'presence' AS approach, all_sessions, presence_view AS view_sessions,
              presence_cart AS cart_sessions, presence_purchase AS purchase_sessions FROM counts
            UNION ALL
            SELECT 'chronological_strict', all_sessions, chronological_view,
              chronological_cart, chronological_purchase FROM counts
        )
        SELECT *,
            view_sessions::DOUBLE / nullif(all_sessions, 0) AS view_share_all_sessions,
            cart_sessions::DOUBLE / nullif(all_sessions, 0) AS cart_share_all_sessions,
            purchase_sessions::DOUBLE / nullif(all_sessions, 0) AS purchase_share_all_sessions,
            cart_sessions::DOUBLE / nullif(view_sessions, 0) AS view_to_cart,
            purchase_sessions::DOUBLE / nullif(cart_sessions, 0) AS cart_to_purchase,
            purchase_sessions::DOUBLE / nullif(view_sessions, 0) AS view_to_purchase,
            1 - cart_sessions::DOUBLE / nullif(view_sessions, 0) AS view_to_cart_dropoff,
            1 - purchase_sessions::DOUBLE / nullif(cart_sessions, 0) AS cart_to_purchase_dropoff
        FROM stages
    """,
    )


def _session_metrics(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    tables = {
        "sessions": _query(
            con,
            """
        SELECT count(*) AS sessions,
          count(*) FILTER (WHERE has_view) AS with_view,
          count(*) FILTER (WHERE has_cart) AS with_cart,
          count(*) FILTER (WHERE has_purchase) AS with_purchase,
          count(*) FILTER (WHERE has_remove) AS with_remove_from_cart,
          count(*) FILTER (WHERE has_view AND has_cart AND has_purchase) AS with_all_three,
          count(*) FILTER (WHERE has_purchase AND NOT has_view) AS purchase_without_view,
          count(*) FILTER (WHERE has_purchase AND NOT has_cart) AS purchase_without_cart,
          count(*) FILTER (WHERE calendar_days > 1) AS spanning_utc_days,
          count(*) FILTER (WHERE missing_times > 0) AS incomplete_timestamps,
          count(*) FILTER (WHERE events = 1) AS single_event_sessions,
          count(*) FILTER (WHERE purchase_events > 1) AS multiple_purchase_events,
          count(*) FILTER (WHERE users > 1) AS multiple_users_after_key_selection,
          count(*) FILTER (WHERE start_time < '2019-10-01'::TIMESTAMPTZ
            OR end_time >= '2019-11-01'::TIMESTAMPTZ) AS outside_october,
          count(*) FILTER (WHERE cast(start_time AS DATE) = '2019-10-01') AS on_first_october_day,
          count(*) FILTER (WHERE cast(end_time AS DATE) = '2019-10-31') AS on_last_october_day
        FROM sessions
    """,
        ),
        "event_combinations": _query(
            con,
            """
        SELECT has_view, has_cart, has_purchase, has_remove, count(*) AS sessions
        FROM sessions GROUP BY ALL ORDER BY sessions DESC
    """,
        ),
        "ordering_anomalies": _query(
            con,
            """
        SELECT
          count(*) FILTER (WHERE first_purchase < first_view) AS purchase_before_first_view,
          count(*) FILTER (WHERE first_cart < first_view) AS cart_before_first_view,
          count(*) FILTER (WHERE first_purchase IS NOT NULL AND
            (first_cart IS NULL OR first_purchase <= first_cart))
            AS purchase_with_no_strictly_preceding_cart,
          count(*) FILTER (WHERE relaxed_complete AND NOT strict_complete)
            AS tie_dependent_complete,
          count(*) FILTER (WHERE relaxed_cart IS NOT NULL AND strict_cart IS NULL)
            AS tie_dependent_cart,
          count(*) FILTER (WHERE has_view AND first_view IS NULL) AS views_without_valid_time
        FROM funnel_sessions
    """,
        ),
        "timestamp_ties": _query(
            con,
            """
        WITH ties AS (
            SELECT session_key, ts, count(*) AS events, count(DISTINCT event_type) AS types
            FROM keyed WHERE ts IS NOT NULL GROUP BY session_key, ts HAVING count(*) > 1
        ) SELECT count(*) AS tied_timestamp_groups, coalesce(sum(events), 0) AS events_in_ties,
            count(DISTINCT session_key) AS sessions_with_ties,
            count(*) FILTER (WHERE types > 1) AS mixed_event_type_ties FROM ties
    """,
        ),
    }
    for column, expression in (
        ("events_per_session", "events"),
        ("products_per_session", "products"),
        ("duration_seconds", "epoch(end_time - start_time)"),
    ):
        tables[column] = _distribution(con, "sessions", expression)
    return tables


def _customer_metrics(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    con.execute("""
        CREATE OR REPLACE TEMP TABLE customers AS
        SELECT user_id, count(*) AS events,
          count(*) FILTER (WHERE event_type = 'purchase') AS purchase_events,
          count(DISTINCT cast(ts AS DATE)) FILTER (WHERE event_type = 'purchase') AS purchase_days,
          count(DISTINCT user_session) FILTER (WHERE event_type = 'purchase') AS purchase_sessions
        FROM current_events WHERE user_id IS NOT NULL GROUP BY user_id
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE purchase_intervals AS
        WITH purchases AS (
            SELECT user_id, user_session, min(ts) AS purchase_time
            FROM current_events
            WHERE user_id IS NOT NULL AND user_session IS NOT NULL AND event_type = 'purchase'
            GROUP BY user_id, user_session
        ), following AS (
            SELECT *, lead(purchase_time) OVER (
                PARTITION BY user_id ORDER BY purchase_time, user_session
            ) AS next_purchase_time,
              min(purchase_time) OVER (PARTITION BY user_id ORDER BY purchase_time
                RANGE BETWEEN INTERVAL '1 microsecond' FOLLOWING AND UNBOUNDED FOLLOWING)
                AS next_strict_purchase_time
            FROM purchases WHERE purchase_time IS NOT NULL
        ) SELECT *, epoch(next_purchase_time - purchase_time) / 86400.0 AS days_to_next
          FROM following
    """)
    tables = {
        "customers": _query(
            con,
            """
        SELECT count(*) AS customers,
          count(*) FILTER (WHERE purchase_events > 0) AS purchasing_customers,
          count(*) FILTER (WHERE purchase_events = 0) AS non_purchasing_customers,
          count(*) FILTER (WHERE purchase_days > 1) AS multiple_purchasing_days,
          count(*) FILTER (WHERE purchase_sessions > 1) AS multiple_purchasing_sessions,
          count(*) FILTER (WHERE purchase_events > 0 AND purchase_sessions = 0)
            AS purchasers_without_known_session,
          count(*) FILTER (WHERE events = 1) AS single_event_customers,
          coalesce(sum(purchase_events), 0) AS purchase_events,
          coalesce(sum(purchase_days), 0) AS customer_purchasing_days,
          coalesce(sum(purchase_sessions), 0) AS customer_purchasing_sessions
        FROM customers
    """,
        ),
        "purchase_session_frequency": _query(
            con,
            """
        SELECT CASE WHEN purchase_sessions = 0 THEN '0 (missing session IDs)'
          WHEN purchase_sessions = 1 THEN '1' WHEN purchase_sessions = 2 THEN '2'
          ELSE '3+' END AS purchasing_sessions, count(*) AS customers
        FROM customers WHERE purchase_events > 0 GROUP BY 1 ORDER BY 1
    """,
        ),
        "purchase_intervals_days": _distribution(con, "purchase_intervals", "days_to_next"),
        "interval_quality": _query(
            con,
            """
            SELECT count(*) FILTER (WHERE days_to_next = 0) AS tied_purchase_session_starts,
                count(*) FILTER (WHERE days_to_next IS NULL) AS right_censored_last_sessions
            FROM purchase_intervals
        """,
        ),
        "daily_purchase_activity": _query(
            con,
            """
            SELECT cast(ts AS DATE) AS day_utc,
                count(*) AS purchase_events, count(DISTINCT user_id) AS purchasing_customers,
                count(DISTINCT (user_id, user_session)) FILTER
                    (WHERE user_session IS NOT NULL AND user_id IS NOT NULL)
                    AS customer_purchasing_sessions
            FROM current_events WHERE event_type = 'purchase' GROUP BY 1 ORDER BY 1
        """,
        ),
        "horizon_feasibility": _query(
            con,
            """
            WITH horizons AS (SELECT unnest([7, 14, 30]) AS horizon_days),
            bounds AS (SELECT min(ts) AS first_event, max(ts) AS last_event FROM current_events)
            SELECT horizon_days, first_event, last_event,
                count(purchase_time) AS known_purchase_session_anchors,
                count(*) FILTER (WHERE purchase_time + horizon_days * INTERVAL '1 day'
                    <= last_event) AS full_followup_anchors,
                count(*) FILTER (WHERE purchase_time + horizon_days * INTERVAL '1 day'
                    <= last_event AND next_strict_purchase_time
                      <= purchase_time + horizon_days * INTERVAL '1 day')
                    AS full_followup_anchors_with_repeat,
                count(DISTINCT user_id) FILTER (WHERE purchase_time
                    + horizon_days * INTERVAL '1 day' <= last_event)
                    AS customers_with_full_followup,
                count(*) FILTER (WHERE purchase_time - horizon_days * INTERVAL '1 day'
                    >= first_event AND purchase_time + horizon_days * INTERVAL '1 day'
                    <= last_event) AS anchors_with_equal_history_and_followup
            FROM horizons CROSS JOIN bounds LEFT JOIN purchase_intervals ON true
            GROUP BY horizon_days, first_event, last_event ORDER BY horizon_days
        """,
        ),
    }
    for column in ("purchase_sessions", "purchase_days"):
        tables[f"{column}_distribution"] = _query(
            con,
            f"""
            SELECT {column}, count(*) AS customers FROM customers
            WHERE purchase_events > 0 GROUP BY 1 ORDER BY 1
        """,
        )
    return tables


def _duplicates(con: duckdb.DuckDBPyConnection, columns: list[str]) -> dict[str, pd.DataFrame]:
    names = ", ".join(quote_identifier(c) for c in columns)
    con.execute(f"""
        CREATE TEMP TABLE duplicate_groups AS
        SELECT {names}, count(*) AS multiplicity FROM events GROUP BY ALL
    """)
    tables = {
        "duplicate_event_types": _query(
            con,
            """
        SELECT event_type, sum(multiplicity) AS raw_events,
            sum(multiplicity - 1) AS excess_duplicate_rows,
            100.0 * sum(multiplicity - 1) / sum(multiplicity) AS duplicate_percentage
        FROM duplicate_groups GROUP BY event_type ORDER BY raw_events DESC
    """,
        ),
        "duplicate_multiplicity": _query(
            con,
            """
        SELECT multiplicity, count(*) AS groups, sum(multiplicity - 1) AS excess_duplicate_rows
        FROM duplicate_groups WHERE multiplicity > 1 GROUP BY 1 ORDER BY 1
    """,
        ),
        "duplicate_days": _query(
            con,
            """
        SELECT cast(cast(event_time AS TIMESTAMPTZ) AS DATE) AS day_utc,
            sum(multiplicity - 1) AS excess_duplicate_rows,
            count(*) FILTER (WHERE multiplicity > 1) AS duplicate_groups
        FROM duplicate_groups GROUP BY 1 ORDER BY 1
    """,
        ),
        "identical_event_timestamp_groups": _query(
            con,
            """
        SELECT count(*) AS groups, coalesce(sum(multiplicity), 0) AS raw_rows,
            coalesce(sum(multiplicity - 1), 0) AS excess_rows
        FROM duplicate_groups WHERE multiplicity > 1 AND event_time IS NOT NULL
    """,
        ),
        "duplicate_missing_sessions": _query(
            con,
            """
        SELECT coalesce(sum(multiplicity - 1), 0) AS excess_rows_with_missing_session
        FROM duplicate_groups WHERE user_session IS NULL
    """,
        ),
    }
    # User/session pairs remain explicit here, independent of the funnel key choice.
    con.execute("""
        CREATE TEMP TABLE session_duplicates AS
        SELECT user_id, user_session, sum(multiplicity - 1) AS excess_rows,
            sum(multiplicity) AS raw_events
        FROM duplicate_groups WHERE user_session IS NOT NULL GROUP BY user_id, user_session
    """)
    tables["duplicate_session_distribution"] = _query(
        con,
        """
        SELECT excess_rows, count(*) AS customer_session_pairs
        FROM session_duplicates GROUP BY 1 ORDER BY 1
    """,
    )
    tables["duplicate_session_summary"] = _query(
        con,
        """
        SELECT count(*) AS customer_session_pairs,
          count(*) FILTER (WHERE excess_rows > 0) AS pairs_with_duplicates,
          max(excess_rows) AS maximum_excess_rows,
          coalesce(sum(excess_rows), 0) AS excess_rows FROM session_duplicates
    """,
    )
    return tables


def _scenario_impact(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for column in tables["raw_counts"].columns:
        raw = tables["raw_counts"].iloc[0][column]
        distinct = tables["deduplicated_counts"].iloc[0][column]
        rows.append((column, raw, distinct, distinct - raw))
    raw_funnel = tables["raw_funnel"].set_index("approach")
    distinct_funnel = tables["deduplicated_funnel"].set_index("approach")
    for approach in raw_funnel.index:
        for metric in ("view_sessions", "cart_sessions", "purchase_sessions", "view_to_purchase"):
            raw = raw_funnel.loc[approach, metric]
            distinct = distinct_funnel.loc[approach, metric]
            rows.append((f"{approach}_{metric}", raw, distinct, distinct - raw))
    return pd.DataFrame(rows, columns=["metric", "raw", "deduplicated", "deduplicated_minus_raw"])


def analyze_behavior(
    input_path: str | Path, progress: Callable[[str], None] | None = None
) -> BehaviorReport:
    """Analyze raw and distinct-row scenarios in an isolated temporary workspace."""
    try:
        with TemporaryDirectory(prefix="ecommerce-analysis-") as scratch:
            with duckdb.connect(
                config={
                    "memory_limit": "2GB",
                    "threads": 2,
                    "preserve_insertion_order": False,
                    "temp_directory": scratch,
                }
            ) as con:
                if progress:
                    progress("Loading and validating source CSV")
                columns = load_events(con, input_path)
                tables = {}
                tables["quality"] = _query(
                    con,
                    """
                    SELECT count(*) AS events, count(DISTINCT user_id) AS unique_customers,
                      count(DISTINCT user_session) AS raw_unique_session_ids,
                      count(*) FILTER (WHERE user_session IS NULL) AS excluded_session_events,
                      count(*) FILTER (WHERE user_id IS NULL) AS excluded_customer_events,
                      count(*) FILTER (WHERE event_time IS NULL) AS missing_timestamps,
                      min(cast(event_time AS TIMESTAMPTZ)) AS first_event,
                      max(cast(event_time AS TIMESTAMPTZ)) AS last_event,
                      count(*) FILTER (WHERE cast(event_time AS TIMESTAMPTZ) < '2019-10-01'
                        OR cast(event_time AS TIMESTAMPTZ) >= '2019-11-01') AS outside_october
                    FROM events
                """,
                )
                tables["missing_values"] = _query(
                    con,
                    " UNION ALL ".join(
                        f"SELECT '{c.replace(chr(39), chr(39) * 2)}' AS column_name, "
                        f"count(*) FILTER (WHERE {quote_identifier(c)} IS NULL) AS missing_values "
                        "FROM events"
                        for c in columns
                    ),
                )
                tables["session_identity"] = _query(
                    con,
                    """
                    WITH ids AS (
                        SELECT user_session, count(DISTINCT user_id) AS known_users,
                            bool_or(user_id IS NULL) AS has_unknown_user
                        FROM events WHERE user_session IS NOT NULL GROUP BY user_session
                    ) SELECT count(*) AS raw_session_ids,
                        count(*) FILTER (WHERE known_users > 1) AS shared_by_multiple_customers,
                        count(*) FILTER (WHERE has_unknown_user) AS ids_with_unknown_customer
                    FROM ids
                """,
                )
                composite = bool(tables["session_identity"].iloc[0].shared_by_multiple_customers)
                if progress:
                    progress("Auditing exact duplicates")
                tables.update(_duplicates(con, columns))
                for scenario, source in (("raw", "events"), ("deduplicated", "duplicate_groups")):
                    if progress:
                        progress(f"Calculating {scenario} session and funnel metrics")
                    con.execute(f"""
                        CREATE OR REPLACE TEMP VIEW current_events AS
                        SELECT {", ".join(quote_identifier(c) for c in columns)},
                            cast(event_time AS TIMESTAMPTZ) AS ts FROM {source}
                    """)
                    prepare_sessions(con, composite)
                    tables[f"{scenario}_funnel"] = _funnel(con)
                    tables[f"{scenario}_counts"] = _query(
                        con,
                        """
                        SELECT count(*) AS events, count(DISTINCT user_id) AS customers,
                          count(DISTINCT user_session) AS raw_unique_session_ids,
                          (SELECT count(*) FROM sessions) AS analytical_sessions,
                          count(*) FILTER (WHERE event_type = 'purchase') AS purchase_events
                        FROM current_events
                    """,
                    )
                    if scenario == "raw":
                        if progress:
                            progress("Calculating customer behavior and horizon feasibility")
                        tables.update(_session_metrics(con))
                        tables.update(_customer_metrics(con))
                tables["scenario_impact"] = _scenario_impact(tables)
                return BehaviorReport(
                    tables,
                    "(user_id, user_session)" if composite else "user_session",
                    str(Path(input_path)),
                )
    except (duckdb.Error, OSError) as exc:
        raise ExplorationError(f"Cannot analyze behavior: {exc}") from exc
