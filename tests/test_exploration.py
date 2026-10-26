"""Behavior checks on small, purpose-built CSV inputs."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from ecommerce_analytics.analytics.exploration import ExplorationError, analyze_csv

HEADER = ["event_time", "event_type", "product_id", "user_id", "user_session", "brand"]
ROWS = [
    ["2019-10-01 00:00:00 UTC", "view", "10", "1", "s1", ""],
    ["2019-10-01 00:00:00 UTC", "view", "10", "1", "s1", ""],
    ["2019-10-02 12:00:00 UTC", "purchase", "20", "2", "s2", "acme"],
    ["", "cart", "20", "1", "", "acme"],
]


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def test_aggregations_and_source_preservation(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "events.csv", ROWS)
    before = path.read_bytes()
    report = analyze_csv(path)
    summary = report.summary.iloc[0]
    assert summary.total_events == 4
    assert summary.unique_customers == 2
    assert summary.unique_sessions == 2
    assert summary.unique_products == 2
    assert str(summary.earliest_event) == "2019-10-01 00:00:00+00:00"
    assert str(summary.latest_event) == "2019-10-02 12:00:00+00:00"
    assert report.duplicate_rows == 1
    missing = report.missing_values.set_index("column").missing_values.to_dict()
    assert missing == dict(zip(HEADER, [1, 0, 0, 0, 1, 2], strict=True))
    assert report.event_types.set_index("event_type").events.to_dict() == {
        "view": 2,
        "cart": 1,
        "purchase": 1,
    }
    assert report.daily_events.events.tolist() == [2, 1, 1]
    assert path.read_bytes() == before


def test_header_only_csv(tmp_path: Path) -> None:
    report = analyze_csv(write_csv(tmp_path / "empty.csv", []))
    assert report.summary.iloc[0].total_events == 0
    assert report.duplicate_rows == 0
    assert report.missing_values.missing_values.sum() == 0
    assert report.daily_events.empty


@pytest.mark.parametrize("contents", ["", "wrong,columns\n1,2\n", 'a\n"unterminated'])
def test_invalid_csv(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "invalid.csv"
    path.write_text(contents)
    with pytest.raises(ExplorationError):
        analyze_csv(path)


def test_invalid_timestamp(tmp_path: Path) -> None:
    row = ROWS[0].copy()
    row[0] = "not a timestamp"
    with pytest.raises(ExplorationError, match="invalid event_time"):
        analyze_csv(write_csv(tmp_path / "invalid-time.csv", [row]))


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ExplorationError, match="not a readable file"):
        analyze_csv(tmp_path / "absent.csv")


def test_cli(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "explore.py"
    path = write_csv(tmp_path / "events.csv", ROWS)
    result = subprocess.run(
        [sys.executable, str(script), "--input", str(path)], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "total_events" in result.stdout
    assert "Exact duplicate rows (beyond the first occurrence): 1" in result.stdout
    result = subprocess.run(
        [sys.executable, str(script), "--input", str(tmp_path / "absent.csv")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr
