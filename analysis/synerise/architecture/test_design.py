"""Local civil-clock and nonexecuting design checks; not live ingestion tests."""

import runpy
from pathlib import Path

ROOT = Path(__file__).parent
MODULE = runpy.run_path(str(ROOT / "schema.py"))


def test_civil_clock_boundaries():
    tick = MODULE["civil_second"]
    assert tick("1970-01-01 00:00:00") == 0
    assert tick("2022-08-15 00:00:00") - tick("2022-08-01 00:00:00") == 14 * 86400
    assert tick("2000-03-01 00:00:00") - tick("2000-02-29 23:59:59") == 1


def test_ddl_is_nonexecuting_and_preserves_sources():
    text = (ROOT / "proposed-ddl.sql").read_text()
    assert all(not line.strip() or line.startswith("--") for line in text.splitlines())
    for source, columns in MODULE["COLUMNS"].items():
        assert f"`{source}`" in text
        for name, kind in columns:
            assert f"`{name}` {kind}" in text
    assert "ReplacingMergeTree" not in text
    assert "DateTime64" not in text
    assert "Tuple(day Date32, second_of_day UInt32)" in text
