"""Read-only, full-file exploratory aggregations using DuckDB."""

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

REQUIRED_COLUMNS = {"event_time", "event_type", "user_id", "user_session", "product_id"}


class ExplorationError(ValueError):
    """An input file cannot be analyzed."""


@dataclass(frozen=True)
class ExplorationReport:
    summary: pd.DataFrame
    event_types: pd.DataFrame
    missing_values: pd.DataFrame
    duplicate_rows: int
    daily_events: pd.DataFrame


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def load_events(connection: duckdb.DuckDBPyConnection, input_path: str | Path) -> list[str]:
    """Load and validate source values without changing their row identity."""
    path = Path(input_path).expanduser()
    if not path.is_file():
        raise ExplorationError(f"Input is not a readable file: {path}")
    if path.stat().st_size == 0:
        raise ExplorationError("Input CSV is empty.")
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute(
        "CREATE TEMP TABLE events AS SELECT * FROM read_csv(?, header=true, all_varchar=true)",
        [str(path)],
    )
    columns = [row[0] for row in connection.execute("DESCRIBE events").fetchall()]
    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        raise ExplorationError(f"Missing required columns: {', '.join(sorted(missing))}")
    invalid_times = connection.execute(
        "SELECT count(*) FROM events WHERE event_time IS NOT NULL "
        "AND try_cast(event_time AS TIMESTAMPTZ) IS NULL"
    ).fetchone()[0]
    if invalid_times:
        raise ExplorationError(f"Found {invalid_times} invalid event_time values.")
    return columns


def analyze_csv(input_path: str | Path) -> ExplorationReport:
    """Aggregate a CSV in DuckDB; only aggregate results become Pandas frames.

    Empty fields are NULL. IDs remain strings to preserve their original values.
    Exact duplicates compare all parsed columns, including NULLs; CSV quoting and
    line endings are not part of row identity. No input data is modified.
    """
    try:
        with duckdb.connect() as connection:
            columns = load_events(connection, input_path)
            summary = connection.execute(
                "SELECT count(*) AS total_events, count(DISTINCT user_id) AS unique_customers, "
                "count(DISTINCT user_session) AS unique_sessions, "
                "count(DISTINCT product_id) AS unique_products, "
                "min(cast(event_time AS TIMESTAMPTZ)) AS earliest_event, "
                "max(cast(event_time AS TIMESTAMPTZ)) AS latest_event FROM events"
            ).df()
            event_types = connection.execute(
                "SELECT event_type, count(*) AS events FROM events "
                "GROUP BY event_type ORDER BY events DESC, event_type"
            ).df()
            expressions = ", ".join(
                f"count(*) FILTER (WHERE {quote_identifier(column)} IS NULL) "
                f"AS {quote_identifier(column)}"
                for column in columns
            )
            counts = connection.execute(f"SELECT {expressions} FROM events").fetchone()
            missing_values = pd.DataFrame({"column": columns, "missing_values": counts})
            duplicate_rows = connection.execute(
                "SELECT (SELECT count(*) FROM events) - "
                "(SELECT count(*) FROM (SELECT DISTINCT * FROM events))"
            ).fetchone()[0]
            daily_events = connection.execute(
                "SELECT cast(cast(event_time AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS DATE) "
                "AS event_date_utc, count(*) AS events FROM events "
                "GROUP BY event_date_utc ORDER BY event_date_utc"
            ).df()
            return ExplorationReport(
                summary, event_types, missing_values, duplicate_rows, daily_events
            )
    except (duckdb.Error, OSError) as exc:
        raise ExplorationError(f"Cannot analyze CSV: {exc}") from exc
