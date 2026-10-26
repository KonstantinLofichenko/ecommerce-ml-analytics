"""Snapshot definitions, censoring, boundary timestamps and future invariance."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from ecommerce_analytics.analytics.exploration import ExplorationError
from ecommerce_analytics.features.customer_snapshots import FEATURES, build_customer_snapshots
from ecommerce_analytics.features.report import write_feature_report

SNAPSHOT = date(2019, 11, 1)


def event(
    timestamp: str | None,
    kind: str = "purchase",
    user: str | None = "buyer",
    session: str | None = "s1",
    product: str | None = "p1",
) -> tuple:
    return timestamp, kind, user, session, product


def database(tmp_path: Path, rows: list[tuple]) -> Path:
    path = tmp_path / "ecommerce.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE raw_events (event_time_utc TIMESTAMP, event_type VARCHAR, "
            "user_id VARCHAR, user_session VARCHAR, product_id VARCHAR)"
        )
        con.executemany(
            "INSERT INTO raw_events VALUES (?::TIMESTAMP, ?, ?, ?, ?)",
            rows + [event("2020-02-20", kind="view", user="coverage")],
        )
        con.execute("CREATE TABLE sessions AS SELECT 'untouched' AS sentinel")
        con.execute("CREATE VIEW customers AS SELECT 'untouched' AS sentinel")
    return path


def build(path: Path, **kwargs) -> dict[str, pd.DataFrame]:
    return build_customer_snapshots(path, [SNAPSHOT], expected={}, **kwargs)


def features(path: Path) -> pd.DataFrame:
    with duckdb.connect(str(path), read_only=True) as con:
        return con.sql(
            "SELECT * FROM customer_snapshot_features ORDER BY prediction_date, user_id"
        ).df()


def test_feature_definitions_nulls_duplicates_and_cross_snapshot_session(tmp_path: Path) -> None:
    rows = [
        event("2019-10-01 12:00:00", session="old"),
        event("2019-10-02", session="cross"),
        event("2019-10-31 23:59:59", "view", session="cross", product="p2"),
        event("2019-10-31 23:59:59", "view", session="cross", product="p2"),
        event("2019-10-31 23:59:59.999999", "cart", session=None, product="p3"),
        event("2019-10-31 12:00:00", "remove_from_cart", session="r1", product="p2"),
        event("2019-11-01", session="cross", product="future-product"),
        event("2019-11-14 23:59:59.999999", session="cross"),
        event("2019-11-15", session="future"),
        event("2019-10-01", user="inactive", session="old"),
        event("2019-10-31", user="null-session", session=None, product=None),
        event("2019-11-10", user="null-session", session=None),
        event("2019-10-31", user="end-boundary"),
        event("2019-11-15", user="end-boundary"),
        event("2019-11-01", user="new-buyer"),
        event("2019-10-31", user=None),
        event("2019-11-01", user=None),
        event(None, user="untimed"),
    ]
    path = database(tmp_path, rows)
    result = build(path)
    frame = features(path).set_index("user_id")
    assert set(frame.index) == {"buyer", "inactive", "null-session", "end-boundary"}
    buyer = frame.loc["buyer"]
    assert buyer.target_14d == 1
    assert buyer.days_since_last_purchase == 30
    assert buyer.days_since_last_event == pytest.approx(1 / 86400 / 1_000_000)
    assert buyer.purchase_sessions_30d == 1
    assert buyer.sessions_30d == 2
    assert buyer.view_events_30d == 2  # Raw identical rows remain counted.
    assert buyer.cart_events_30d == 1
    assert buyer.remove_events_30d == 1
    assert buyer.purchase_events_30d == 1
    assert buyer.distinct_products_30d == 3
    assert buyer.historical_purchasing_sessions == 2
    inactive = frame.loc["inactive"]
    assert inactive.days_since_last_purchase == 31
    assert inactive.days_since_last_event == 31
    assert inactive.historical_purchasing_sessions == 1
    assert (inactive[[f for f in FEATURES if f.endswith("30d")]] == 0).all()
    unknown_session = frame.loc["null-session"]
    assert unknown_session.purchase_events_30d == 1
    assert unknown_session.purchase_sessions_30d == 0
    assert unknown_session.sessions_30d == 0
    assert unknown_session.historical_purchasing_sessions == 0
    assert unknown_session.distinct_products_30d == 0
    assert unknown_session.target_14d == 1
    assert frame.loc["end-boundary"].target_14d == 0
    audit = result["validation"]
    assert not audit[[c for c in audit if c.endswith("_errors")]].to_numpy().any()
    assert result["null_checks"].nulls.sum() == 0
    comparison = result["label_definition_comparison"].iloc[0]
    assert comparison.event_target_positives == 2
    assert comparison.new_session_positives == 0
    assert comparison.event_only_positives == 2
    assert comparison.known_session_positives == 1
    with duckdb.connect(str(path), read_only=True) as con:
        assert con.sql("SELECT count(*) FROM raw_events").fetchone()[0] == len(rows) + 1
        assert con.sql("SELECT * FROM sessions").fetchone()[0] == "untouched"
        assert con.sql("SELECT * FROM customers").fetchone()[0] == "untouched"
    build(path)
    assert len(features(path)) == 4  # A rebuild replaces rather than appends.


@pytest.mark.parametrize(
    ("timestamp", "target"),
    [
        ("2019-10-31 23:59:59.999999", 0),
        ("2019-11-01 00:00:00", 1),
        ("2019-11-14 23:59:59.999999", 1),
        ("2019-11-15 00:00:00", 0),
        ("2019-11-16 00:00:00", 0),
    ],
)
def test_target_half_open_boundaries(tmp_path: Path, timestamp: str, target: int) -> None:
    path = database(tmp_path, [event("2019-10-01"), event(timestamp)])
    build(path)
    assert features(path).iloc[0].target_14d == target


@pytest.mark.parametrize(
    ("timestamp", "views"),
    [
        ("2019-10-01 23:59:59.999999", 0),
        ("2019-10-02 00:00:00", 1),
        ("2019-10-31 23:59:59.999999", 1),
        ("2019-11-01 00:00:00", 0),
    ],
)
def test_trailing_half_open_boundaries(tmp_path: Path, timestamp: str, views: int) -> None:
    path = database(tmp_path, [event("2019-10-01"), event(timestamp, kind="view")])
    build(path)
    assert features(path).iloc[0].view_events_30d == views


def test_all_future_changes_leave_features_invariant(tmp_path: Path) -> None:
    path = database(tmp_path, [event("2019-10-20"), event("2019-10-31", "view")])
    build(path)
    before = features(path)
    with duckdb.connect(str(path)) as con:
        con.executemany(
            "INSERT INTO raw_events VALUES (?::TIMESTAMP, ?, ?, ?, ?)",
            [
                event("2019-11-01", "purchase", session="new"),
                event("2019-11-07", "cart", session="new", product="new-product"),
                event("2019-11-20", "remove_from_cart"),
                event("2019-12-01", "purchase"),
            ],
        )
    build(path)
    after = features(path)
    pd.testing.assert_frame_equal(
        before.drop(columns="target_14d"), after.drop(columns="target_14d")
    )
    assert before.iloc[0].target_14d == 0
    assert after.iloc[0].target_14d == 1


def test_distinct_composite_session_keys_and_multiple_snapshots(tmp_path: Path) -> None:
    path = database(
        tmp_path,
        [
            event("2019-10-31", user="u1", session="same"),
            event("2019-10-31", user="u2", session="same"),
            event("2019-11-01", user="u3", session="same"),
        ],
    )
    build_customer_snapshots(path, [SNAPSHOT, date(2019, 12, 1)], expected={})
    frame = features(path)
    assert len(frame) == 5
    assert not frame.duplicated(["prediction_date", "user_id"]).any()
    assert frame.historical_purchasing_sessions.tolist() == [1] * 5
    assert set(frame[frame.prediction_date == pd.Timestamp(SNAPSHOT)].user_id) == {"u1", "u2"}


def test_reconciliation_is_explicit_and_export_is_aggregate_only(tmp_path: Path) -> None:
    path = database(tmp_path, [event("2019-10-20"), event("2019-11-03")])
    tables = build_customer_snapshots(path, [SNAPSHOT], expected={SNAPSHOT: (10, 8)})
    row = tables["snapshot_summary"].iloc[0]
    assert row.eligible_difference == -9
    assert row.positive_difference == -7
    assert row.reconciliation.startswith("DISCREPANCY")
    write_feature_report(tables, path, tmp_path / "report.md", tmp_path / "output")
    assert "DISCREPANCY" in (tmp_path / "report.md").read_text()
    assert len(list((tmp_path / "output").glob("*.csv"))) == 6
    assert all("user_id" not in table.columns for table in tables.values())
    with pytest.raises(ValueError, match="overwrite"):
        write_feature_report(tables, path, path, tmp_path / "output")


def test_empty_eligible_population(tmp_path: Path) -> None:
    path = database(tmp_path, [event("2019-11-01")])
    tables = build(path)
    assert features(path).empty
    assert tables["snapshot_summary"].iloc[0].eligible_customers == 0
    assert tables["snapshot_summary"].iloc[0].positive_labels == 0


def test_transaction_rollback_and_followup_guard(tmp_path: Path, monkeypatch) -> None:
    path = database(tmp_path, [event("2019-10-20")])
    build(path)
    before = features(path)
    with pytest.raises(ExplorationError, match="follow-up"):
        build_customer_snapshots(path, [date(2020, 2, 10)])

    def fail(con):
        raise ExplorationError("deliberate validation failure")

    monkeypatch.setattr("ecommerce_analytics.features.customer_snapshots._validate_snapshot", fail)
    with pytest.raises(ExplorationError, match="deliberate"):
        build(path)
    pd.testing.assert_frame_equal(before, features(path))


def test_invalid_dates_and_missing_database(tmp_path: Path) -> None:
    path = database(tmp_path, [event("2019-10-20")])
    with pytest.raises(ExplorationError, match="not found"):
        build_customer_snapshots(tmp_path / "missing.duckdb")
    with pytest.raises(ExplorationError, match="unique UTC"):
        build_customer_snapshots(path, [SNAPSHOT, SNAPSHOT])
    with pytest.raises(ExplorationError, match="unique UTC"):
        build_customer_snapshots(path, [])


def test_cli(tmp_path: Path) -> None:
    path = database(tmp_path, [event("2019-10-20")])
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_customer_features.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--database",
            str(path),
            "--prediction-date",
            "2019-11-01",
            "--report",
            str(tmp_path / "report.md"),
            "--output",
            str(tmp_path / "output"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "report.md").exists()
    assert "DISCREPANCY" in result.stdout
