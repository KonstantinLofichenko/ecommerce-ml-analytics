"""Bounded, isolated staging loads with reconciliation-gated Atomic publication."""

import fcntl
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import file_digest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import duckdb

from ecommerce_analytics.ingestion.clickhouse import (
    ClickHouse,
    MigrationError,
    TransportError,
    identifier,
)
from ecommerce_analytics.ingestion.reconciliation import (
    check_destination,
    compare,
    ddl,
    json_select,
    profile,
    source_schema,
)


def emit(event: str, **fields) -> None:
    print(
        json.dumps(
            {"timestamp": datetime.now(UTC).isoformat(), "event": event, **fields}, default=str
        ),
        flush=True,
    )


def table_uuid(client: ClickHouse, database: str, table: str) -> str | None:
    identifier(database)
    identifier(table)
    rows = client.query(
        f"SELECT toString(uuid) AS uuid FROM system.tables "
        f"WHERE database='{database}' AND name='{table}'"
    )
    return rows[0]["uuid"] if rows else None


def publish(client: ClickHouse, database: str, stage: str, previous_uuid: str | None) -> str | None:
    """Never retry an EXCHANGE: an acknowledgement loss must not swap twice."""
    target = f"{identifier(database)}.raw_events"
    staging = f"{identifier(database)}.{identifier(stage)}"
    staged_uuid = table_uuid(client, database, stage)
    if table_uuid(client, database, "raw_events") != previous_uuid:
        raise MigrationError("Destination changed during the load; publication cancelled.")
    sql = (
        f"EXCHANGE TABLES {target} AND {staging}"
        if previous_uuid
        else f"RENAME TABLE {staging} TO {target}"
    )
    try:
        client.command(sql)
    except TransportError:
        # Resolve ambiguous publication by immutable table UUID, not by repeating the write.
        if table_uuid(client, database, "raw_events") != staged_uuid:
            raise MigrationError(
                "Publication acknowledgement lost; inspect UUIDs before recovery."
            ) from None
    if table_uuid(client, database, "raw_events") != staged_uuid:
        raise MigrationError("Published UUID did not match the validated staging table.")
    return stage if previous_uuid else None


def migrate(
    source: Path,
    client: ClickHouse,
    output: Path,
    batch_size: int = 50000,
    attempts: int = 2,
    database: str = "ecommerce",
    expected_rows: int | None = None,
    force_reload: bool = False,
    validate_only: bool = False,
    progress: Callable = emit,
) -> dict:
    if not source.is_file():
        raise MigrationError(f"DuckDB file not found: {source}")
    if not 1 <= batch_size <= 250000 or not 1 <= attempts <= 5:
        raise MigrationError("Batch size must be 1..250000; attempts must be 1..5.")
    identifier(database)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (output / ".migration.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise MigrationError("Another local migration uses this output directory.") from None
        with TemporaryDirectory(prefix="ecommerce-migration-") as scratch:
            with duckdb.connect(
                str(source),
                read_only=True,
                config={
                    "memory_limit": "2GB",
                    "threads": 2,
                    "temp_directory": scratch,
                },
            ) as con:
                con.execute("SET TimeZone='UTC'")
                con.execute("BEGIN TRANSACTION")

                def file_hash():
                    with source.open("rb") as file:
                        return file_digest(file, "sha256").hexdigest()

                source_hash = file_hash()
                identity = {
                    "filename": source.name,
                    "bytes": source.stat().st_size,
                    "mtime_ns": source.stat().st_mtime_ns,
                    "sha256": source_hash,
                }
                (output / "source_file_before.json").write_text(json.dumps(identity, indent=2))

                def record_result(result):
                    if file_hash() != source_hash:
                        raise MigrationError("DuckDB source file changed during migration.")
                    result["source_sha256"] = source_hash
                    result["source_file_unchanged"] = True
                    (output / "result.json").write_text(json.dumps(result, indent=2))
                    if (
                        result["status"] == "published"
                        and not (output / "initial_result.json").exists()
                    ):
                        (output / "initial_result.json").write_text(json.dumps(result, indent=2))

                source_schema(con)
                engine = client.query(
                    f"SELECT engine FROM system.databases WHERE name='{database}'"
                )
                if not engine or engine[0]["engine"] != "Atomic":
                    raise MigrationError("Destination database must exist with engine Atomic.")
                progress("source_reconciliation_started")
                reference = profile(con, progress=progress)
                total = reference["_global"][0]["rows"]
                if expected_rows is not None and total != expected_rows:
                    raise MigrationError(f"Expected {expected_rows} source rows; found {total}.")
                (output / "reference.json").write_text(json.dumps(reference, indent=2))
                previous_uuid = table_uuid(client, database, "raw_events")
                if previous_uuid:
                    check_destination(client, database, "raw_events")
                    actual = profile(con, client, f"{identifier(database)}.raw_events", progress)
                    differences = compare(reference, actual)
                    (output / "differences.json").write_text(json.dumps(differences, indent=2))
                    if not differences and not force_reload:
                        result = {
                            "status": "validated_noop",
                            "rows": total,
                            "inserted_rows": 0,
                            "duration_seconds": round(time.monotonic() - started, 3),
                            "differences": [],
                            "reference": reference,
                            "destination": actual,
                        }
                        record_result(result)
                        progress("migration_complete", status=result["status"], rows=total)
                        return result
                    if validate_only:
                        raise MigrationError(
                            "Destination reconciliation failed; see differences.json."
                        )
                elif validate_only:
                    raise MigrationError("No published raw_events table exists.")
                for attempt in range(1, attempts + 1):
                    stage = "_raw_events_stage_" + uuid4().hex
                    qualified = f"{identifier(database)}.{identifier(stage)}"
                    progress("staging_started", stage=stage, attempt=attempt)
                    client.command(ddl(database, stage))
                    state = {
                        "stage": stage,
                        "source_rows": total,
                        "previous_uuid": previous_uuid,
                        "status": "loading",
                        "staging_uuid": table_uuid(client, database, stage),
                        "acknowledged_rows": 0,
                    }
                    state_path = output / f"{stage}.json"
                    state_path.write_text(json.dumps(state, indent=2))
                    load_start = time.monotonic()
                    try:
                        cursor = con.execute(json_select())
                        loaded, batches = 0, 0
                        while rows := cursor.fetchmany(batch_size):
                            payload = ("\n".join(r[0] for r in rows) + "\n").encode()
                            # No write retry: uncertain commits abandon this staging attempt.
                            client.insert(qualified, payload)
                            loaded += len(rows)
                            batches += 1
                            state["acknowledged_rows"] = loaded
                            state_path.write_text(json.dumps(state, indent=2))
                            progress(
                                "batch_inserted",
                                attempt=attempt,
                                batch=batches,
                                rows=loaded,
                                total=total,
                                rows_per_second=round(loaded / (time.monotonic() - load_start)),
                            )
                        state["status"] = "validating"
                        state_path.write_text(json.dumps(state, indent=2))
                        actual = profile(con, client, qualified, progress)
                        differences = compare(reference, actual)
                        (output / "differences.json").write_text(json.dumps(differences, indent=2))
                        if differences:
                            raise MigrationError(
                                "Staging reconciliation failed; see differences.json."
                            )
                        load_seconds = time.monotonic() - load_start
                    except TransportError as exc:
                        state["error"] = str(exc)
                        state["status"] = "abandoned_uncertain_insert_or_read"
                        state_path.write_text(json.dumps(state, indent=2))
                        progress("staging_abandoned", stage=stage, attempt=attempt, error=str(exc))
                        if attempt == attempts:
                            raise
                        time.sleep(min(2 ** (attempt - 1), 4))
                        continue
                    except Exception:
                        state["status"] = "failed_unpublished"
                        state_path.write_text(json.dumps(state, indent=2))
                        raise
                    # Record intent before the atomic swap; never retry a swap blindly.
                    state["status"] = "publishing"
                    state_path.write_text(json.dumps(state, indent=2))
                    retained = publish(client, database, stage, previous_uuid)
                    state.update(
                        status="published",
                        retained_previous_table=retained,
                        published_uuid=table_uuid(client, database, "raw_events"),
                    )
                    state_path.write_text(json.dumps(state, indent=2))
                    result = {
                        "status": "published",
                        "rows": total,
                        "inserted_rows": loaded,
                        "batch_size": batch_size,
                        "batches": batches,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "load_and_validation_seconds": round(load_seconds, 3),
                        "retained_previous_table": retained,
                        "differences": [],
                        "reference": reference,
                        "destination": actual,
                    }
                    record_result(result)
                    progress(
                        "migration_complete",
                        status="published",
                        rows=total,
                        duration_seconds=result["duration_seconds"],
                    )
                    return result
    raise AssertionError("unreachable")
