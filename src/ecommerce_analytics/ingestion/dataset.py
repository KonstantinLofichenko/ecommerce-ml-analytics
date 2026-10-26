"""Rebuild a single persistent DuckDB dataset from immutable local monthly CSVs."""

from collections.abc import Callable, Mapping
from datetime import date
from hashlib import file_digest
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

MONTH_FILES = {
    "2019-10": "2019-Oct.csv",
    "2019-11": "2019-Nov.csv",
    "2019-12": "2019-Dec.csv",
    "2020-01": "2020-Jan.csv",
    "2020-02": "2020-Feb.csv",
}
RESERVED_COLUMNS = {"month", "event_time_utc"}


def _fingerprint(path: Path) -> str:
    with path.open("rb") as file:
        return file_digest(file, "sha256").hexdigest()


def _load_months(
    con: duckdb.DuckDBPyConnection, sources: Mapping[str, Path], progress: Callable[[str], None]
) -> list[str]:
    columns: list[str] = []
    con.execute("""
        CREATE OR REPLACE TABLE dataset_sources (
            month VARCHAR, filename VARCHAR, bytes BIGINT, sha256 VARCHAR, rows BIGINT
        )
    """)
    for month, path in sorted(sources.items()):
        progress(f"Loading {month}: {path.name}")
        before_stat = path.stat()
        fingerprint = _fingerprint(path)
        current = load_events(con, path)
        if RESERVED_COLUMNS.intersection(current):
            raise ExplorationError("CSV uses reserved month/event_time_utc columns.")
        if not columns:
            columns = current
            con.execute("""
                CREATE OR REPLACE TABLE raw_events AS
                SELECT *, ''::VARCHAR AS month,
                    cast(event_time AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS event_time_utc
                FROM events WHERE false
            """)
        if set(current) != set(columns):
            raise ExplorationError(f"Column schema differs for {month}: {path.name}")
        names = ", ".join(quote_identifier(c) for c in columns)
        con.execute(
            f"""
            INSERT INTO raw_events
            SELECT {names}, ?, cast(event_time AS TIMESTAMPTZ) AT TIME ZONE 'UTC'
            FROM events
        """,
            [month],
        )
        rows = con.execute("SELECT count(*) FROM events").fetchone()[0]
        after_stat = path.stat()
        if (before_stat.st_size, before_stat.st_mtime_ns) != (
            after_stat.st_size,
            after_stat.st_mtime_ns,
        ):
            raise ExplorationError(f"Source changed during ingestion: {path.name}")
        con.execute(
            "INSERT INTO dataset_sources VALUES (?, ?, ?, ?, ?)",
            [month, path.name, before_stat.st_size, fingerprint, rows],
        )
        con.execute("DROP TABLE events")
    return columns


def _build_sessions(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TEMP VIEW current_events AS
        SELECT *, event_time_utc::TIMESTAMPTZ AS ts FROM raw_events
    """)
    prepare_sessions(con, composite=True)
    con.execute("""
        CREATE OR REPLACE TABLE session_summary AS
        WITH month_counts AS (
            SELECT struct_pack(user_id := user_id, user_session := user_session) AS session_key,
              count(DISTINCT month) AS source_months,
              count(DISTINCT date_trunc('month', event_time_utc)) AS calendar_months
            FROM raw_events WHERE user_session IS NOT NULL GROUP BY 1
        )
        SELECT f.session_key, f.user_id, f.user_session,
          f.start_time AT TIME ZONE 'UTC' AS session_start_utc,
          f.end_time AT TIME ZONE 'UTC' AS session_end_utc,
          epoch(f.end_time - f.start_time) AS duration_seconds,
          f.events AS event_count, f.products AS distinct_products,
          f.purchase_events, f.calendar_days, m.source_months, m.calendar_months,
          f.missing_times AS events_missing_time,
          f.has_view, f.has_cart, f.has_purchase, f.has_remove AS has_remove_from_cart,
          f.has_view AND f.has_cart AS presence_view_cart,
          f.has_view AND f.has_cart AND f.has_purchase AS presence_complete,
          f.first_view IS NOT NULL AS chronological_view,
          f.strict_cart IS NOT NULL AS chronological_view_cart,
          f.strict_complete AS chronological_complete,
          f.relaxed_complete AND NOT f.strict_complete AS tie_dependent_complete,
          f.first_purchase AT TIME ZONE 'UTC' AS first_purchase_utc
        FROM funnel_sessions f JOIN month_counts m USING (session_key)
    """)
    # Free full-row intermediates before customer aggregation and duplicate comparison.
    for table in ("funnel_sessions", "stage_carts", "sessions", "keyed"):
        con.execute(f"DROP TABLE {table}")


def _build_customers(con: duckdb.DuckDBPyConnection, months: list[str]) -> None:
    con.execute("""
        CREATE OR REPLACE TABLE customer_monthly_summary AS
        WITH activity AS (
            SELECT user_id, strftime(event_time_utc, '%Y-%m') AS month,
              count(*) AS event_count,
              count(*) FILTER (WHERE event_type = 'purchase') AS purchase_events,
              count(DISTINCT user_session) FILTER (WHERE event_type = 'purchase')
                AS purchasing_sessions
            FROM raw_events
            WHERE user_id IS NOT NULL AND event_time_utc IS NOT NULL GROUP BY 1, 2
        ), anchors AS (
            SELECT user_id, strftime(first_purchase_utc, '%Y-%m') AS month,
              count(*) AS sessions_first_purchased_in_month
            FROM session_summary
            WHERE user_id IS NOT NULL AND first_purchase_utc IS NOT NULL GROUP BY 1, 2
        ) SELECT a.*, coalesce(b.sessions_first_purchased_in_month, 0)
            AS sessions_first_purchased_in_month
        FROM activity a LEFT JOIN anchors b USING (user_id, month)
    """)
    monthly_columns = ", ".join(
        f"coalesce(max(m.purchasing_sessions) FILTER (WHERE m.month = '{month}'), 0) "
        f"AS purchasing_sessions_{month.replace('-', '_')}"
        for month in months
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE customer_summary AS
        WITH customers AS (
            SELECT user_id, min(event_time_utc) AS first_observed_utc,
              max(event_time_utc) AS last_observed_utc, count(*) AS event_count,
              count(*) FILTER (WHERE event_type = 'purchase') AS purchase_events,
              count(*) FILTER (WHERE event_time_utc IS NULL) AS events_missing_time,
              count(*) FILTER (WHERE event_type = 'purchase' AND user_session IS NULL)
                AS purchase_events_missing_session,
              count(*) FILTER (WHERE event_type = 'purchase' AND event_time_utc IS NULL)
                AS purchase_events_missing_time,
              count(DISTINCT user_session) FILTER (WHERE event_type = 'purchase')
                AS purchasing_sessions
            FROM raw_events WHERE user_id IS NOT NULL GROUP BY user_id
        ), monthly AS (
            SELECT c.user_id, {monthly_columns} FROM customers c
            LEFT JOIN customer_monthly_summary m USING (user_id) GROUP BY c.user_id
        ) SELECT c.*, m.* EXCLUDE (user_id) FROM customers c JOIN monthly m USING (user_id)
    """)


def _comparison_tables(
    con: duckdb.DuckDBPyConnection, columns: list[str]
) -> dict[str, pd.DataFrame]:
    names = ", ".join(quote_identifier(c) for c in columns)
    con.execute(f"""
        CREATE OR REPLACE VIEW events_exact_deduplicated AS
        SELECT {names}, min(month) AS month, min(event_time_utc) AS event_time_utc
        FROM raw_events GROUP BY {names}
    """)
    # One execution of the comparison view; this temporary copy is never persisted.
    con.execute("""
        CREATE TEMP TABLE comparison_events AS SELECT * FROM events_exact_deduplicated
    """)
    tables = {}
    for name, key in (
        ("monthly_counts", "month"),
        ("event_type_counts", "event_type"),
        ("monthly_event_types", "month, event_type"),
    ):
        join = " AND ".join(
            f"r.{k.strip()} IS NOT DISTINCT FROM d.{k.strip()}" for k in key.split(",")
        )
        selected_keys = ", ".join("r." + k.strip() for k in key.split(","))
        tables[name] = con.execute(f"""
            WITH r AS (SELECT {key}, count(*) AS raw_rows FROM raw_events GROUP BY {key}),
            d AS (SELECT {key}, count(*) AS comparison_rows FROM comparison_events GROUP BY {key})
            SELECT {selected_keys},
              raw_rows, coalesce(comparison_rows, 0) AS comparison_rows,
              raw_rows - coalesce(comparison_rows, 0) AS excess_duplicate_rows,
              100.0 * (raw_rows - coalesce(comparison_rows, 0)) / raw_rows
                AS raw_duplicate_percentage,
              0.0 AS comparison_duplicate_percentage
            FROM r LEFT JOIN d ON {join} ORDER BY {selected_keys}
        """).df()
    tables["overview"] = con.execute("""
        SELECT (SELECT count(*) FROM raw_events) AS raw_rows,
          (SELECT count(*) FROM comparison_events) AS comparison_rows,
          (SELECT count(*) FROM session_summary) AS sessions,
          (SELECT count(*) FROM customer_summary) AS known_customers,
          (SELECT min(event_time_utc) FROM raw_events) AS first_event_utc,
          (SELECT max(event_time_utc) FROM raw_events) AS last_event_utc
    """).df()
    tables["quality_by_month"] = con.execute("""
        SELECT month, count(*) AS raw_rows,
          count(*) FILTER (WHERE user_session IS NULL) AS excluded_session_events,
          count(*) FILTER (WHERE user_id IS NULL) AS excluded_customer_events,
          count(*) FILTER (WHERE event_time_utc IS NULL) AS missing_timestamps,
          count(*) FILTER (WHERE strftime(event_time_utc, '%Y-%m') != month)
            AS timestamp_source_month_mismatches
        FROM raw_events GROUP BY month ORDER BY month
    """).df()
    tables["session_quality"] = con.execute("""
        SELECT count(*) FILTER (WHERE calendar_days > 1) AS crossing_utc_days,
          count(*) FILTER (WHERE calendar_months > 1) AS crossing_utc_months,
          count(*) FILTER (WHERE source_months > 1) AS spanning_source_files,
          count(*) FILTER (WHERE user_id IS NULL) AS sessions_with_unknown_customer,
          count(*) FILTER (WHERE presence_complete) AS presence_complete,
          count(*) FILTER (WHERE chronological_complete) AS chronological_complete,
          count(*) FILTER (WHERE tie_dependent_complete) AS tie_dependent_complete
        FROM session_summary
    """).df()
    tables["sources"] = con.execute("SELECT * FROM dataset_sources ORDER BY month").df()
    con.execute("DROP TABLE comparison_events")
    return tables


def build_dataset(
    sources: Mapping[str, Path], database: Path, progress: Callable[[str], None] | None = None
) -> dict[str, pd.DataFrame]:
    """Transactionally rebuild this project's managed tables/views; preserve unrelated objects.

    Source keys are provenance months (YYYY-MM), not filters on event timestamps.
    Missing event times are retained; malformed nonempty times fail validation.
    """
    log = progress or (lambda message: None)
    if not sources:
        raise ExplorationError("At least one monthly source is required.")
    sources = {month: Path(path).expanduser() for month, path in sources.items()}
    for month, path in sources.items():
        try:
            if date.fromisoformat(month + "-01").strftime("%Y-%m") != month:
                raise ValueError
        except ValueError as exc:
            raise ExplorationError(f"Invalid month: {month}") from exc
        if not path.is_file():
            raise ExplorationError(f"Input is not a readable file: {path}")
        if database.resolve() == path.resolve():
            raise ExplorationError("Database path would overwrite a source CSV.")
    if len({p.resolve() for p in sources.values()}) != len(sources):
        raise ExplorationError("Each month must have a distinct source file.")
    database.parent.mkdir(parents=True, exist_ok=True)
    try:
        with TemporaryDirectory(prefix="ecommerce-build-") as scratch:
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
                con.execute("BEGIN TRANSACTION")
                try:
                    # Known views must be removed before their backing tables are replaced.
                    for view in ("events_exact_deduplicated", "sessions", "customers"):
                        con.execute(f"DROP VIEW IF EXISTS {view}")
                    columns = _load_months(con, sources, log)
                    log("Building cross-file sessions and shared funnel flags")
                    _build_sessions(con)
                    log("Building customer and monthly purchase summaries")
                    _build_customers(con, sorted(sources))
                    log("Measuring exact-duplicate comparison view")
                    tables = _comparison_tables(con, columns)
                    con.execute("CREATE VIEW sessions AS SELECT * FROM session_summary")
                    con.execute("CREATE VIEW customers AS SELECT * FROM customer_summary")
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                con.execute("CHECKPOINT")
                log(f"Database ready: {database}")
                return tables
    except (duckdb.Error, OSError) as exc:
        raise ExplorationError(f"Cannot build dataset: {exc}") from exc
