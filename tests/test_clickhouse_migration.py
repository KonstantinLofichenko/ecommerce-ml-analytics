"""Raw migration contract and opt-in real ClickHouse interruption/retry tests."""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest

from ecommerce_analytics.ingestion.clickhouse import (
    MigrationError,
    TransportError,
    configured_client,
    environment,
    identifier,
)
from ecommerce_analytics.ingestion.migration import migrate, table_uuid
from ecommerce_analytics.ingestion.reconciliation import (
    SOURCE_COLUMNS,
    canonical_sql,
    compare,
    profile,
    source_schema,
)


def make_source(path: Path) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE raw_events ("
            + ",".join(
                f'"{c}" {"TIMESTAMP" if c == "event_time_utc" else "VARCHAR"}'
                for c in SOURCE_COLUMNS
            )
            + ")"
        )
        row = [
            "2019-10-31 23:59:59.123456 UTC",
            "purchase",
            "001",
            "02",
            None,
            'é\tline\n"quote"',
            "-79.37",
            "0001",
            None,
            "2019-10",
            datetime(2019, 10, 31, 23, 59, 59, 123456),
        ]
        other = [
            "2019-11-01 00:00:00 UTC",
            "view",
            "",
            None,
            "1:é",
            "",
            "02.60",
            None,
            "shared",
            "2019-11",
            datetime(2019, 11, 1),
        ]
        missing = [None, None, None, None, None, None, None, None, None, "2019-11", None]
        con.executemany(
            "INSERT INTO raw_events VALUES (" + ",".join("?" for _ in SOURCE_COLUMNS) + ")",
            [row, row, other, missing],
        )


def test_source_schema_nulls_duplicates_and_money(tmp_path: Path) -> None:
    path = tmp_path / "source.duckdb"
    make_source(path)
    with duckdb.connect(str(path), read_only=True) as con:
        source_schema(con)
        result = profile(con)
    assert result["_global"][0] == {"rows": 4, "distinct_users": 1}
    october = result["2019-10"]
    assert october["aggregates"][0]["price_minor_units"] == -15874
    assert october["aggregates"][0]["null_user_session"] == 2
    assert october["duplicates"] == [{"multiplicity": 2, "groups": 1}]
    assert october["aggregates"][0]["minimum_time"] == "2019-10-31 23:59:59.123456"
    assert result["2019-11"]["aggregates"][0]["null_price"] == 1
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE raw_events SET price='1.001'")
        with pytest.raises(MigrationError, match="invalid"):
            source_schema(con)
        con.execute("ALTER TABLE raw_events DROP COLUMN brand")
        with pytest.raises(MigrationError, match="schema"):
            source_schema(con)


def test_canonical_utf8_null_and_empty_are_distinct(tmp_path: Path) -> None:
    path = tmp_path / "source.duckdb"
    make_source(path)
    with duckdb.connect(str(path), read_only=True) as con:
        row = con.execute(f"SELECT {canonical_sql('duck')} FROM raw_events LIMIT 1").fetchone()[0]
        values = [
            "2019-10-31 23:59:59.123456 UTC",
            "purchase",
            "001",
            "02",
            None,
            'é\tline\n"quote"',
            "-79.37",
            "0001",
            None,
            "2019-10",
            "2019-10-31 23:59:59.123456",
            "-7937",
        ]
        expected = "".join("-1:" if v is None else f"{len(v.encode())}:{v}" for v in values)
        assert row == expected
        assert (
            hashlib.md5(row.encode()).hexdigest()
            == con.execute(
                f"SELECT md5({canonical_sql('duck')}) FROM raw_events LIMIT 1"
            ).fetchone()[0]
        )
    assert compare({"a": 1}, {"a": 2})
    assert not compare({"a": 1}, {"a": 1})
    with pytest.raises(MigrationError):
        identifier("x; DROP DATABASE ecommerce")


@pytest.fixture
def live_client():
    if os.environ.get("ECOMMERCE_CLICKHOUSE_TESTS") != "1":
        pytest.skip("Set ECOMMERCE_CLICKHOUSE_TESTS=1 to run against local ClickHouse")
    client = configured_client(environment(), "ADMIN")
    database = "ecommerce_migration_test_" + uuid4().hex
    client.command(f"CREATE DATABASE {identifier(database)} ENGINE=Atomic")
    try:
        yield client, database
    finally:
        # Only the UUID-scoped test database is removed; no production or AIS data.
        client.command(f"DROP DATABASE {identifier(database)} SYNC")


def test_live_idempotency_and_uncertain_insert_recovery(
    tmp_path: Path, live_client, monkeypatch
) -> None:
    client, database = live_client
    path = tmp_path / "source.duckdb"
    make_source(path)
    output = tmp_path / "output"

    def run(**kw):
        return migrate(
            path,
            client,
            output,
            batch_size=2,
            database=database,
            progress=lambda *a, **k: None,
            **kw,
        )

    first = run()
    assert first["rows"] == 4 and first["differences"] == []
    original_uuid = table_uuid(client, database, "raw_events")
    assert run()["status"] == "validated_noop"
    assert table_uuid(client, database, "raw_events") == original_uuid
    # Simulate an INSERT committed by the server, with a lost HTTP response.
    original_insert = client.insert

    def lost_ack(table, payload):
        original_insert(table, payload)
        raise TransportError("deliberate lost insert acknowledgement")

    monkeypatch.setattr(client, "insert", lost_ack)
    with pytest.raises(TransportError):
        run(force_reload=True, attempts=1)
    assert table_uuid(client, database, "raw_events") == original_uuid
    assert int(client.query(f"SELECT count(*) AS n FROM {database}.raw_events")[0]["n"]) == 4
    states = [json.loads(p.read_text()) for p in output.glob("_raw_events_stage_*.json")]
    assert any(s["status"].startswith("abandoned") for s in states)
    monkeypatch.setattr(client, "insert", original_insert)
    recovered = run(force_reload=True)
    assert recovered["differences"] == []
    assert recovered["retained_previous_table"]
    assert run()["status"] == "validated_noop"


def test_live_lost_exchange_ack_is_not_repeated(tmp_path: Path, live_client, monkeypatch) -> None:
    client, database = live_client
    path = tmp_path / "source.duckdb"
    make_source(path)

    def run(**kw):
        return migrate(
            path,
            client,
            tmp_path / "out",
            batch_size=2,
            database=database,
            progress=lambda *a, **k: None,
            **kw,
        )

    run()
    previous = table_uuid(client, database, "raw_events")
    original_command = client.command
    exchanges = []

    def lost_ack(sql, parameters=None):
        original_command(sql, parameters)
        if sql.startswith("EXCHANGE TABLES"):
            exchanges.append(sql)
            raise TransportError("deliberate lost exchange response")

    monkeypatch.setattr(client, "command", lost_ack)
    result = run(force_reload=True)
    assert len(exchanges) == 1
    assert table_uuid(client, database, "raw_events") != previous
    assert result["rows"] == 4 and result["differences"] == []


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("event_time", "not-a-timestamp"),
        ("month", None),
        ("month", "2019-99"),
        ("price", "1.001"),
        ("price", "NaN"),
    ],
)
def test_invalid_source_rejected_before_load(tmp_path: Path, column: str, value) -> None:
    path = tmp_path / "source.duckdb"
    make_source(path)
    with duckdb.connect(str(path)) as con:
        con.execute(f'UPDATE raw_events SET "{column}" = ?', [value])
        with pytest.raises(MigrationError, match="invalid"):
            source_schema(con)


def test_live_validation_failure_preserves_destination(tmp_path: Path, live_client, monkeypatch):
    client, database = live_client
    path = tmp_path / "source.duckdb"
    make_source(path)
    out = tmp_path / "out"
    migrate(path, client, out, batch_size=2, database=database, progress=lambda *a, **k: None)
    previous = table_uuid(client, database, "raw_events")
    original_insert = client.insert

    def corrupt_stage(table, payload):
        original_insert(table, payload)
        client.command(
            f"ALTER TABLE {table} UPDATE brand='corrupt' "
            "WHERE month='2019-10' SETTINGS mutations_sync=1"
        )

    monkeypatch.setattr(client, "insert", corrupt_stage)
    with pytest.raises(MigrationError, match="reconciliation failed"):
        migrate(
            path,
            client,
            out,
            batch_size=2,
            database=database,
            force_reload=True,
            progress=lambda *a, **k: None,
        )
    assert table_uuid(client, database, "raw_events") == previous
    differences = json.loads((out / "differences.json").read_text())
    october = next(d for d in differences if d["partition"] == "2019-10")
    assert october["reference"]["aggregates"][0]["rows"] == 2
    assert october["destination"]["aggregates"][0]["rows"] == 2
    assert (
        october["reference"]["aggregates"][0]["checksum_sum_1"]
        != october["destination"]["aggregates"][0]["checksum_sum_1"]
    )


def test_role_env_preserves_existing_credentials_and_repeated_file_bytes(tmp_path: Path):
    from ecommerce_analytics.ingestion.permissions import ensure_role_environment

    path = tmp_path / ".env"
    path.write_text(
        "CLICKHOUSE_USER=ecommerce_app\nCLICKHOUSE_PASSWORD=keep-admin-value\n"
        "CLICKHOUSE_BI_PASSWORD=keep-bi-value\n"
    )
    ensure_role_environment(path)
    first = path.read_bytes()
    assert b"CLICKHOUSE_PASSWORD=keep-admin-value" in first
    assert b"CLICKHOUSE_BI_PASSWORD=keep-bi-value" in first
    assert b"CLICKHOUSE_INGEST_USER=ecommerce_ingest" in first
    ensure_role_environment(path)
    assert path.read_bytes() == first
