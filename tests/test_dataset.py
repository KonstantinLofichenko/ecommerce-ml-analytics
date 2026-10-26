"""Persistent dataset invariants across source and calendar boundaries."""

import csv
from pathlib import Path

import duckdb
import pytest

from ecommerce_analytics.analytics.exploration import ExplorationError
from ecommerce_analytics.ingestion.dataset import build_dataset

HEADER = ["event_time", "event_type", "product_id", "user_id", "user_session", "brand"]


def write(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def test_raw_duplicates_cross_midnight_and_cross_month(tmp_path: Path) -> None:
    view = ["2019-10-31 23:59:59 UTC", "view", "p1", "u1", "s1", ""]
    cart = ["2019-11-01 00:00:00 UTC", "cart", "p2", "u1", "s1", ""]
    purchase = ["2019-11-01 00:00:01 UTC", "purchase", "p3", "u1", "s1", ""]
    missing_session = ["2019-11-01 01:00:00 UTC", "purchase", "p4", "u2", "", ""]
    unknown_user = ["2019-11-01 02:00:00 UTC", "view", "p5", "", "s2", ""]
    sources = {
        "2019-10": write(tmp_path / "oct.csv", [view, view]),
        "2019-11": write(tmp_path / "nov.csv", [cart, purchase, missing_session, unknown_user]),
    }
    before = {month: path.read_bytes() for month, path in sources.items()}
    database = tmp_path / "dataset.duckdb"
    tables = build_dataset(sources, database)
    assert tables["monthly_counts"].raw_rows.tolist() == [2, 4]
    assert tables["monthly_counts"].comparison_rows.tolist() == [1, 4]
    assert tables["monthly_counts"].raw_duplicate_percentage.tolist() == [50, 0]
    assert tables["quality_by_month"].excluded_session_events.tolist() == [0, 1]
    with duckdb.connect(str(database), read_only=True) as con:
        assert con.sql("SELECT count(*) FROM raw_events").fetchone()[0] == 6
        assert con.sql("SELECT count(*) FROM events_exact_deduplicated").fetchone()[0] == 5
        session = con.sql("SELECT * FROM sessions WHERE user_id = 'u1'").df().iloc[0]
        assert session.event_count == 4
        assert session.calendar_days == 2
        assert session.calendar_months == 2
        assert session.source_months == 2
        assert session.duration_seconds == 2
        assert session.chronological_complete
        assert session.presence_complete
        assert str(session.session_start_utc) == "2019-10-31 23:59:59"
        assert session.session_key == {"user_id": "u1", "user_session": "s1"}
        assert con.sql("SELECT count(*) FROM customers").fetchone()[0] == 2
        customer = con.sql("SELECT * FROM customers WHERE user_id = 'u2'").df().iloc[0]
        assert customer.purchase_events == 1
        assert customer.purchase_events_missing_session == 1
        assert customer.purchasing_sessions == 0
        assert customer.purchasing_sessions_2019_11 == 0
        assert con.sql("SELECT count(*) FROM sessions WHERE user_id IS NULL").fetchone()[0] == 1
    assert {month: path.read_bytes() for month, path in sources.items()} == before
    # Rebuilding must not append rows or delete unrelated objects.
    with duckdb.connect(str(database)) as con:
        con.execute("CREATE TABLE unrelated AS SELECT 7 AS value")
    build_dataset(sources, database)
    with duckdb.connect(str(database), read_only=True) as con:
        assert con.sql("SELECT count(*) FROM raw_events").fetchone()[0] == 6
        assert con.sql("SELECT value FROM unrelated").fetchone()[0] == 7


def test_purchase_session_month_attribution_and_exact_source_identity(tmp_path: Path) -> None:
    october = ["2019-10-31 23:59:59 UTC", "purchase", "p1", "u1", "shared", ""]
    november = ["2019-11-01 00:00:00 UTC", "purchase", "p2", "u1", "shared", ""]
    other_user = ["2019-11-01 00:00:01 UTC", "purchase", "p2", "u2", "shared", ""]
    missing_time = ["", "purchase", "p2", "u2", "unknown-time", ""]
    sources = {
        "2019-10": write(tmp_path / "oct.csv", [october]),
        "2019-11": write(tmp_path / "nov.csv", [october, november, other_user, missing_time]),
    }
    database = tmp_path / "dataset.duckdb"
    tables = build_dataset(sources, database)
    assert tables["quality_by_month"].timestamp_source_month_mismatches.tolist() == [0, 1]
    with duckdb.connect(str(database)) as con:
        # Cross-file duplicates compare original values, not added source-month metadata.
        assert con.sql("SELECT count(*) FROM events_exact_deduplicated").fetchone()[0] == 4
        customer = con.sql("SELECT * FROM customers WHERE user_id='u1'").df().iloc[0]
        assert customer.purchasing_sessions == 1
        assert customer.purchasing_sessions_2019_10 == 1
        assert customer.purchasing_sessions_2019_11 == 1
        assert con.sql(
            "SELECT sessions_first_purchased_in_month FROM "
            "customer_monthly_summary WHERE user_id='u1' ORDER BY month"
        ).fetchall() == [(1,), (0,)]
        assert con.sql("SELECT count(*) FROM sessions").fetchone()[0] == 3
        assert (
            con.sql(
                "SELECT purchase_events_missing_time FROM customers WHERE user_id='u2'"
            ).fetchone()[0]
            == 1
        )
        con.execute("SET TimeZone = 'Asia/Tokyo'")
        assert (
            str(
                con.sql("SELECT first_observed_utc FROM customers WHERE user_id='u1'").fetchone()[0]
            )
            == "2019-10-31 23:59:59"
        )


def test_failed_rebuild_preserves_previous_dataset(tmp_path: Path) -> None:
    path = write(tmp_path / "oct.csv", [["2019-10-01 00:00:00 UTC", "view", "p1", "u1", "s1", ""]])
    database = tmp_path / "dataset.duckdb"
    build_dataset({"2019-10": path}, database)
    path.write_text("wrong,schema\n1,2\n")
    with pytest.raises(ExplorationError):
        build_dataset({"2019-10": path}, database)
    with duckdb.connect(str(database), read_only=True) as con:
        assert con.sql("SELECT count(*) FROM raw_events").fetchone()[0] == 1
        assert con.sql("SELECT count(*) FROM sessions").fetchone()[0] == 1
        assert con.sql("SELECT count(*) FROM events_exact_deduplicated").fetchone()[0] == 1


def test_invalid_sources(tmp_path: Path) -> None:
    database = tmp_path / "dataset.duckdb"
    with pytest.raises(ExplorationError, match="At least one"):
        build_dataset({}, database)
    with pytest.raises(ExplorationError, match="not a readable file"):
        build_dataset({"2019-10": tmp_path / "absent.csv"}, database)
    path = write(tmp_path / "source.csv", [])
    with pytest.raises(ExplorationError, match="Invalid month"):
        build_dataset({"2019-99": path}, database)
    with pytest.raises(ExplorationError, match="overwrite"):
        build_dataset({"2019-10": path}, path)
    with pytest.raises(ExplorationError, match="distinct source"):
        build_dataset({"2019-10": path, "2019-11": path}, database)


def test_cli_default_database_path(tmp_path: Path) -> None:
    import subprocess
    import sys

    from ecommerce_analytics.ingestion.dataset import MONTH_FILES

    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    for month, filename in MONTH_FILES.items():
        write(raw / filename, [[month + "-01 00:00:00 UTC", "view", "p1", "u1", month, ""]])
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_dataset.py"
    result = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    database = tmp_path / "data" / "processed" / "ecommerce.duckdb"
    assert database.is_file()
    with duckdb.connect(str(database), read_only=True) as con:
        assert con.sql("SELECT count(*) FROM raw_events").fetchone()[0] == 5
    assert (tmp_path / "docs" / "reports" / "phase-1.3a-october-2019-february-2020.md").is_file()
