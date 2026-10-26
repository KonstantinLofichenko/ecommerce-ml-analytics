"""Explicit opt-in: at most 10k source rows/type into owned temporary ClickHouse database."""

import argparse
import hashlib
import io
import json
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
from schema import COLUMNS, civil_second, ddl

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment

ROOT = Path(__file__).parent
LIMITS = {
    "max_threads": "1",
    "max_insert_threads": "1",
    "max_memory_usage": str(64 * 1024**2),
    "input_format_parallel_parsing": "0",
    "async_insert": "0",
    "insert_deduplicate": "0",
    "input_format_null_as_default": "0",
    "max_insert_block_size": "10000",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-isolated-poc", action="store_true")
    args = parser.parse_args()
    if not args.execute_isolated_poc:
        parser.error("Requires explicit isolated POC opt-in; never a full ingestion command")
    c = configured_client(environment(), "ADMIN")

    def q(sql):
        return json.loads(c._request(sql + " FORMAT JSON", parameters=LIMITS))["data"]

    def command(sql):
        c.command(sql, LIMITS)

    memory = q(
        "SELECT metric,value FROM system.asynchronous_metrics WHERE metric IN "
        "('MemoryResident','CGroupMemoryUsed','CGroupMemoryTotal')"
    )
    metrics = {x["metric"]: int(float(x["value"])) for x in memory}
    assert metrics["CGroupMemoryTotal"] - metrics["CGroupMemoryUsed"] > 256 * 1024**2, metrics
    assert metrics["MemoryResident"] < 1200 * 1024**2, metrics
    assert int(q("SELECT count() AS n FROM system.merges")[0]["n"]) == 0
    assert (
        int(q("SELECT count() AS n FROM system.processes WHERE query_id!=currentQueryID()")[0]["n"])
        == 0
    )

    def raw_state():
        return q(
            "SELECT toString(uuid) AS uuid,total_rows FROM system.tables "
            "WHERE database='ecommerce' AND name='raw_events'"
        )

    before = raw_state()
    assert len(before) == 1 and int(before[0]["total_rows"]) == 20692840
    run = uuid4()
    database = "synerise_poc_" + run.hex
    result = {
        "run_id": str(run),
        "database": database,
        "version": q("SELECT version() AS v")[0]["v"],
        "rows_per_source": 10000,
        "limits": LIMITS,
        "memory_before": memory,
        "raw_before": before,
        "measurements": [],
        "completed": False,
    }
    (ROOT / "benchmark-results.json").write_text(json.dumps(result, indent=2))
    manifest = json.loads(Path("analysis/synerise/download-manifest.json").read_text())
    hashes = {Path(x["name"]).stem: x["sha256"] for x in manifest["members"]}
    command(f"CREATE DATABASE {database} ENGINE=Atomic COMMENT 'synerise-poc-{run}'")
    db_uuid = q(f"SELECT toString(uuid) AS uuid FROM system.databases WHERE name='{database}'")[0][
        "uuid"
    ]
    try:
        for index, source in enumerate(
            ("page_visit", "add_to_cart", "product_buy", "product_properties")
        ):
            original = Path(f"data/external/synerise/source/{source}.parquet")
            digest = hashlib.sha256()
            with original.open("rb") as source_file:
                while chunk := source_file.read(1024 * 1024):
                    digest.update(chunk)
            assert digest.hexdigest() == hashes[source]
            started = time.monotonic()
            batch = next(
                pq.ParquetFile(original).iter_batches(
                    batch_size=10000, row_groups=[0], use_threads=False
                )
            )
            table = pa.Table.from_batches([batch])
            assert table.num_rows == 10000 and not any(
                column.null_count for column in table.columns
            )
            parquet = io.BytesIO()
            pq.write_table(table, parquet, compression="snappy")
            sample = parquet.getvalue()
            expected = Counter(
                tuple(row[n] for n, _ in COLUMNS[source]) for row in table.to_pylist()
            )
            result.setdefault("sample_preparation_seconds", {})[source] = time.monotonic() - started
            for method in (
                ("native_parquet", "pyarrow_arrow")
                if index % 2 == 0
                else ("pyarrow_arrow", "native_parquet")
            ):
                name = source + "_" + method
                command(
                    ddl(
                        database,
                        name,
                        source,
                        hashes[source],
                        manifest["archive_sha256"],
                        str(run),
                        str(uuid4()),
                    )
                )
                cols = ",".join("`" + n + "`" for n, _ in COLUMNS[source])
                started = time.monotonic()
                if method == "native_parquet":
                    payload = sample
                    fmt = "Parquet"
                else:
                    reader = pq.ParquetFile(io.BytesIO(sample))
                    bounded = next(reader.iter_batches(batch_size=10000, use_threads=False))
                    sink = pa.BufferOutputStream()
                    with ipc.new_stream(sink, bounded.schema) as writer:
                        writer.write_batch(bounded)
                    payload = sink.getvalue().to_pybytes()
                    fmt = "ArrowStream"
                prepared = time.monotonic() - started
                query_id = "synerise_poc_" + uuid4().hex
                insert_start = time.monotonic()
                c._request(
                    f"INSERT INTO {database}.{name} ({cols}) FORMAT {fmt}",
                    payload,
                    {**LIMITS, "query_id": query_id},
                )
                seconds = time.monotonic() - insert_start
                destination = q(f"SELECT {cols} FROM {database}.{name}")
                actual = Counter(
                    tuple(int(row[n]) if kind == "Int64" else row[n] for n, kind in COLUMNS[source])
                    for row in destination
                )
                assert actual == expected
                stats = q(
                    f"SELECT sum(rows) AS rows,sum(bytes_on_disk) AS bytes_on_disk,"
                    f"sum(data_compressed_bytes) AS compressed_bytes FROM system.parts "
                    f"WHERE database='{database}' AND table='{name}' AND active"
                )[0]
                measurement = {
                    "source": source,
                    "method": method,
                    "rows": 10000,
                    "payload_bytes": len(payload),
                    "preparation_seconds": prepared,
                    "insert_seconds": seconds,
                    "rows_per_second": 10000 / seconds,
                    "query_id": query_id,
                    "parts": stats,
                    "exact_multiset_match": True,
                    "excess_sample_duplicates": sum(expected.values()) - len(expected),
                    "parsing_errors": 0,
                }
                if source != "product_properties":
                    check = q(
                        f"SELECT countIf(toString(source_day)!=substring(timestamp,1,10)) AS bad,"
                        f"min(source_second) AS first_tick,max(source_second) AS last_tick "
                        f"FROM {database}.{name}"
                    )[0]
                    assert int(check["bad"]) == 0
                    expected_ticks = [civil_second(row["timestamp"]) for row in table.to_pylist()]
                    assert int(check["first_tick"]) == min(expected_ticks)
                    assert int(check["last_tick"]) == max(expected_ticks)

                    measurement["clock_check"] = check
                measurement["memory_sample"] = q(
                    "SELECT metric,value FROM system.asynchronous_metrics "
                    "WHERE metric IN ('MemoryResident','CGroupMemoryUsed')"
                )
                result["measurements"].append(measurement)
                (ROOT / "benchmark-results.json").write_text(json.dumps(result, indent=2))
                print(source, method, f"{seconds:.4f}s exact match", flush=True)
        # Logs are asynchronous; do not globally flush them or change logging settings.
        for _ in range(12):
            logs = q(
                "SELECT query_id,memory_usage,written_rows,query_duration_ms FROM system.query_log "
                "WHERE type='QueryFinish' AND startsWith(query_id,'synerise_poc_')"
            )
            by_id = {x["query_id"]: x for x in logs}
            if all(x["query_id"] in by_id for x in result["measurements"]):
                break
            time.sleep(1)
        for measurement in result["measurements"]:
            measurement["query_log"] = by_id.get(measurement["query_id"])
        assert raw_state() == before
        result["raw_after"] = raw_state()
        result["completed"] = True
    finally:
        owned = q(
            f"SELECT toString(uuid) AS uuid,comment FROM system.databases WHERE name='{database}'"
        )
        if owned and owned[0]["uuid"] == db_uuid and owned[0]["comment"] == f"synerise-poc-{run}":
            command(f"DROP DATABASE {database} SYNC")
            result["cleanup_verified"] = not q(
                f"SELECT name FROM system.databases WHERE name='{database}'"
            )
        else:
            result["cleanup_verified"] = False
        (ROOT / "benchmark-results.json").write_text(json.dumps(result, indent=2) + "\n")
    assert result["cleanup_verified"]


if __name__ == "__main__":
    main()
