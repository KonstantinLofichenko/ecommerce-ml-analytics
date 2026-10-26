"""Opt-in bounded comparison, reusing architecture DDL and existing HTTP client."""

import argparse
import hashlib
import io
import json
import resource
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema import COLUMNS, civil_second, ddl  # noqa: E402

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment  # noqa: E402

ROOT = Path(__file__).resolve().parent
LIMITS = {
    "max_threads": "1",
    "max_insert_threads": "1",
    "max_memory_usage": str(128 * 1024**2),
    "input_format_parallel_parsing": "0",
    "async_insert": "0",
    "insert_deduplicate": "0",
    "input_format_null_as_default": "0",
    "max_insert_block_size": "10000",
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def canonical(rows):
    """Sorted row hashes retain multiplicity, distinguish typed null/string/int values."""
    hashes = sorted(
        hashlib.sha256(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()).digest()
        for row in rows
    )
    return hashlib.sha256(b"".join(hashes)).hexdigest()


def publishable(states, expected_sources):
    return set(states) == set(expected_sources) and all(v == "validated" for v in states.values())


class Monitor:
    def __init__(self, query):
        self.query = query
        self.samples = []
        self.stop = threading.Event()
        self.error = None

    def sample(self):
        values = self.query(
            "SELECT metric,value FROM system.asynchronous_metrics WHERE metric IN "
            "('MemoryResident','CGroupMemoryUsed','CGroupMemoryTotal')"
        )
        m = {r["metric"]: int(float(r["value"])) for r in values}
        m["python_rss"] = (
            int(
                subprocess.check_output(
                    ["ps", "-o", "rss=", "-p", str(__import__("os").getpid())]
                ).strip()
            )
            * 1024
        )
        m["merges"] = int(self.query("SELECT count() AS n FROM system.merges")[0]["n"])
        m["disk_free"] = int(self.query("SELECT min(free_space) AS n FROM system.disks")[0]["n"])
        m["server_tracked_memory"] = int(
            self.query("SELECT value FROM system.metrics WHERE metric='MemoryTracking'")[0]["value"]
        )
        m["time_monotonic"] = time.monotonic()
        self.samples.append(m)
        if (
            m["CGroupMemoryTotal"] - m["CGroupMemoryUsed"] < 2 * 1024**3
            or m["MemoryResident"] > 4 * 1024**3
            or m["disk_free"] < 20 * 1024**3
            or m["merges"] > 8
            or m["server_tracked_memory"] > 4 * 1024**3
        ):
            raise RuntimeError("Resource safety gate breached")

    def loop(self):
        while not self.stop.wait(0.25):
            try:
                self.sample()
            except Exception as e:
                self.error = type(e).__name__ + ": " + str(e)
                return

    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()
        self.sample()
        if self.error:
            raise RuntimeError(self.error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-isolated-benchmark", action="store_true")
    args = parser.parse_args()
    if not args.execute_isolated_benchmark:
        parser.error("Explicit opt-in required")
    c = configured_client(environment(), "ADMIN")

    def q(sql):
        return json.loads(c._request(sql + " FORMAT JSON", parameters=LIMITS))["data"]

    def command(sql):
        c.command(sql, LIMITS)

    def inventory():
        return q(
            "SELECT database,name,toString(uuid) AS "
            "uuid,create_table_query,total_rows FROM system.tables WHERE database IN "
            "('ecommerce','ecommerce_analytics') ORDER BY database,name"
        )

    def grants():
        return q(
            "SELECT * FROM system.grants ORDER BY "
            "user_name,role_name,access_type,database,table,column"
        )

    paths = [
        Path("data/external/synerise/synerise_dataset.tar.gz"),
        Path("data/processed/ecommerce.duckdb"),
    ]
    paths += sorted(Path("data/external/synerise/source").glob("*.parquet"))
    paths += [Path("compose.yaml"), Path("infra/clickhouse/development.xml"), Path(".env")]
    paths += sorted(
        p
        for p in Path("dbt").rglob("*")
        if p.is_file() and not any(x in p.parts for x in ("target", "logs", "dbt_packages"))
    )
    baseline = {str(p): sha(p) for p in paths}
    before, grants_before = inventory(), grants()
    assert int(q("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]) == 20692840
    docker = json.loads(
        subprocess.check_output(["docker", "inspect", "ecommerce-ml-clickhouse-1"])
    )[0]
    assert docker["HostConfig"]["Memory"] == 8 * 1024**3
    assert docker["HostConfig"]["NanoCpus"] == 2000000000
    assert docker["State"]["Health"]["Status"] == "healthy"
    assert (
        int(
            q("SELECT value FROM system.server_settings WHERE name='max_server_memory_usage'")[0][
                "value"
            ]
        )
        == 6 * 1024**3
    )
    assert not q("SELECT query_id FROM system.processes WHERE query_id!=currentQueryID()")
    assert int(q("SELECT count() AS n FROM system.merges")[0]["n"]) == 0
    run = uuid4()
    db = "synerise_bench_" + run.hex
    comment = "synerise-benchmark-" + str(run)
    result = {
        "run_id": str(run),
        "database": db,
        "version": q("SELECT version() AS v")[0]["v"],
        "started": datetime.now().isoformat(),
        "limits": LIMITS,
        "docker_memory": docker["HostConfig"]["Memory"],
        "docker_nanocpus": docker["HostConfig"]["NanoCpus"],
        "server_memory": 6 * 1024**3,
        "trials": [],
        "schema_checks": [],
        "recovery": {},
        "completed": False,
    }
    manifest = json.loads(Path("analysis/synerise/download-manifest.json").read_text())
    hashes = {Path(x["name"]).stem: x["sha256"] for x in manifest["members"]}
    for source in COLUMNS:
        assert baseline[f"data/external/synerise/source/{source}.parquet"] == hashes[source]
    command(f"CREATE DATABASE {db} ENGINE=Atomic COMMENT '{comment}'")
    db_uuid = q(f"SELECT toString(uuid) AS uuid FROM system.databases WHERE name='{db}'")[0]["uuid"]

    def save():
        (ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n")

    def create(source, name):
        attempt = str(uuid4())
        command(
            ddl(db, name, source, hashes[source], manifest["archive_sha256"], str(run), attempt)
        )
        return attempt

    def insert(source, name, table, method):
        cols = ",".join("`" + n + "`" for n, _ in COLUMNS[source])
        start = time.monotonic()
        if method == "http_parquet":
            sink = io.BytesIO()
            pq.write_table(table, sink, compression="snappy")
            payload, fmt = sink.getvalue(), "Parquet"
        else:
            sink = pa.BufferOutputStream()
            with ipc.new_stream(sink, table.schema) as writer:
                writer.write_table(table)
            payload, fmt = sink.getvalue().to_pybytes(), "ArrowStream"
        prepared = time.monotonic() - start
        query_id = "synerise_bench_" + uuid4().hex
        start = time.monotonic()
        try:
            c._request(
                f"INSERT INTO {db}.{name} ({cols}) FORMAT {fmt}",
                payload,
                {**LIMITS, "query_id": query_id},
            )
        except Exception as error:
            result.setdefault("failed_requests", []).append(
                {
                    "query_id": query_id,
                    "source": source,
                    "method": method,
                    "error": str(error),
                    "retries": 0,
                }
            )
            raise
        return {
            "query_id": query_id,
            "preparation_seconds": prepared,
            "transfer_seconds": time.monotonic() - start,
            "payload_bytes": len(payload),
        }

    def reconcile(source, name, rows, attempt):
        cols = ",".join("`" + n + "`" for n, _ in COLUMNS[source])
        extra = (
            ""
            if source == "product_properties"
            else (
                ",toString(source_day) AS civil_day,tupleElement(event_time_source,2) AS "
                "civil_sod,source_second AS civil_tick"
            )
        )
        actual = q(
            f"SELECT "
            f"{cols},_source_file,_source_sha256,_archive_sha256,toString(_release_id)"
            f" AS release,toString(_attempt_id) AS attempt{extra} FROM {db}.{name}"
        )
        normalized = []
        for row in actual:
            normalized.append(
                tuple(int(row[n]) if kind == "Int64" else row[n] for n, kind in COLUMNS[source])
            )
            assert (
                row["_source_file"] == source + ".parquet"
                and row["_source_sha256"] == hashes[source]
            )
            assert (
                row["_archive_sha256"] == manifest["archive_sha256"]
                and row["release"] == str(run)
                and row["attempt"] == attempt
            )
            if extra:
                dt = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                assert row["civil_day"] == row["timestamp"][:10]
                assert int(row["civil_sod"]) == dt.hour * 3600 + dt.minute * 60 + dt.second
                assert int(row["civil_tick"]) == civil_second(row["timestamp"])
        expected = [tuple(r[n] for n, _ in COLUMNS[source]) for r in rows]
        assert Counter(normalized) == Counter(expected)
        return {
            "rows": len(actual),
            "exact_multiset_match": True,
            "all_row_clock_and_provenance_match": True,
            "canonical_sha256": canonical(normalized),
            "excess_duplicates": len(expected) - len(set(expected)),
        }

    try:
        # Both input formats: signed IDs, extreme Int64, Unicode, duplicates, leap/day boundaries.
        for source in COLUMNS:
            schema = pa.schema(
                [(n, pa.int64() if k == "Int64" else pa.string()) for n, k in COLUMNS[source]]
            )
            fixture = []
            for i, stamp in enumerate(
                ("1969-12-31 23:59:59", "2000-02-29 23:59:59", "2022-08-01 00:00:00")
            ):
                fixture.append(
                    {
                        n: (
                            -9223372036854775808 if i == 0 else 9223372036854775807 if i == 1 else 0
                        )
                        if k == "Int64"
                        else stamp
                        if n == "timestamp"
                        else "żółć 東京 🛒 01 -2  003\t4"
                        for n, k in COLUMNS[source]
                    }
                )
            fixture += [dict(fixture[-1]) for _ in range(12)]
            for method in ("http_parquet", "arrow_stream"):
                name = "fixture_" + source + "_" + method
                attempt = create(source, name)
                insert(source, name, pa.Table.from_pylist(fixture, schema=schema), method)
                checks = reconcile(source, name, fixture, attempt)
                # Query shape usable by dbt: named tuple components, source-day and numeric windows.
                if source != "product_properties":
                    assert (
                        int(
                            q(
                                f"SELECT count() AS n FROM {db}.{name} WHERE source_second>=0 AND "
                                f"source_day>=toDate32('2000-01-01')"
                            )[0]["n"]
                        )
                        == 14
                    )
                result["schema_checks"].append({"source": source, "method": method, **checks})
                command(f"DROP TABLE {db}.{name} SYNC")
                for invalid in ("null", "clock") if source != "product_properties" else ("null",):
                    bad = dict(fixture[0])
                    bad["timestamp" if invalid == "clock" else COLUMNS[source][0][0]] = (
                        "2022-02-30 25:00:00" if invalid == "clock" else None
                    )
                    name = "bad_" + source + "_" + method + "_" + invalid
                    create(source, name)
                    rejected = False
                    try:
                        insert(source, name, pa.Table.from_pylist([bad], schema=schema), method)
                    except Exception:
                        rejected = True
                    assert rejected, (source, method, invalid)
                    result["schema_checks"].append(
                        {"source": source, "method": method, "rejected": invalid}
                    )
                    command(f"DROP TABLE {db}.{name} SYNC")
        for size in (10000, 50000, 100000):
            for index, source in enumerate(COLUMNS):
                for repetition in range(2):
                    methods = (
                        ("http_parquet", "arrow_stream")
                        if (index + repetition) % 2 == 0
                        else ("arrow_stream", "http_parquet")
                    )
                    for method in methods:
                        name = "trial_" + uuid4().hex
                        attempt = create(source, name)
                        rows, batches = [], []
                        started = time.monotonic()
                        with Monitor(q) as monitor:
                            reader = pq.ParquetFile(
                                f"data/external/synerise/source/{source}.parquet"
                            )
                            iterator = reader.iter_batches(
                                batch_size=10000, row_groups=[0], use_threads=False
                            )
                            read_seconds = 0.0
                            for _ in range(size // 10000):
                                t = time.monotonic()
                                batch = next(iterator)
                                read_seconds += time.monotonic() - t
                                assert batch.num_rows == 10000 and not any(
                                    x.null_count for x in batch.columns
                                )
                                if monitor.error:
                                    raise RuntimeError(monitor.error)
                                batches.append(
                                    insert(source, name, pa.Table.from_batches([batch]), method)
                                )
                                rows.extend(batch.to_pylist())
                        wall = time.monotonic() - started
                        integrity = reconcile(source, name, rows, attempt)
                        stats = q(
                            "SELECT count() AS parts,sum(rows) AS rows,"
                            "sum(data_compressed_bytes) AS "
                            "compressed_bytes,sum(bytes_on_disk) AS bytes_on_disk "
                            "FROM system.parts "
                            f"WHERE database='{db}' AND table='{name}' AND active"
                        )[0]
                        transfer = sum(x["transfer_seconds"] for x in batches)
                        preparation = sum(x["preparation_seconds"] for x in batches)
                        trial = {
                            "source": source,
                            "method": method,
                            "rows": size,
                            "batch_size": 10000,
                            "row_group": 0,
                            "row_offset": 0,
                            "repetition": repetition,
                            "read_seconds": read_seconds,
                            "preparation_seconds": preparation,
                            "transfer_seconds": transfer,
                            "pipeline_seconds": read_seconds + preparation + transfer,
                            "monitored_wall_seconds": wall,
                            "rows_per_transfer_second": size / transfer,
                            "rows_per_pipeline_second": size
                            / (read_seconds + preparation + transfer),
                            "batches": batches,
                            "storage": stats,
                            "integrity": integrity,
                            "resource_samples": monitor.samples,
                            "python_lifetime_peak_bytes": resource.getrusage(
                                resource.RUSAGE_SELF
                            ).ru_maxrss,
                            "errors": 0,
                            "retries": 0,
                        }
                        result["trials"].append(trial)
                        save()
                        print(
                            size,
                            source,
                            repetition,
                            method,
                            round(transfer, 3),
                            "seconds, reconciled",
                            flush=True,
                        )
                        command(f"DROP TABLE {db}.{name} SYNC")
        # Run finalize.py separately for guarded live recovery exercises.
        # Wait for naturally flushed query logs; never flush system logs globally.
        ids = [b["query_id"] for t in result["trials"] for b in t["batches"]]
        logs = {}
        for _ in range(20):
            logs = {
                x["query_id"]: x
                for x in q(
                    "SELECT "
                    "query_id,memory_usage,written_rows,query_duration_ms,ProfileEvents['UserTimeMicroseconds']"
                    " AS cpu_user_us,ProfileEvents['SystemTimeMicroseconds'] AS cpu_system_us"
                    " FROM system.query_log WHERE type='QueryFinish' AND "
                    "startsWith(query_id,'synerise_bench_')"
                )
            }
            if all(i in logs for i in ids):
                break
            time.sleep(1)
        for trial in result["trials"]:
            trial["query_logs"] = [logs.get(b["query_id"]) for b in trial["batches"]]
        result["completed"] = True
    finally:
        owned = q(f"SELECT toString(uuid) AS uuid,comment FROM system.databases WHERE name='{db}'")
        assert owned and owned[0]["uuid"] == db_uuid and owned[0]["comment"] == comment
        command(f"DROP DATABASE {db} SYNC")
        result["cleanup_verified"] = not q(f"SELECT name FROM system.databases WHERE name='{db}'")
        result["rees46_exact_rows_after"] = int(
            q("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]
        )
        result["production_table_identity_schema_counts_unchanged"] = inventory() == before
        result["grants_unchanged"] = grants() == grants_before
        after = {str(p): sha(p) for p in paths}
        result["protected_files_unchanged"] = after == baseline
        result["protected_file_count"] = len(paths)
        # Do not publish even hashed credential material; retain only equality.
        result["source_hashes"] = {s: hashes[s] for s in COLUMNS}
        result["finished"] = datetime.now().isoformat()
        save()
        assert (
            result["cleanup_verified"]
            and result["production_table_identity_schema_counts_unchanged"]
            and result["grants_unchanged"]
            and result["protected_files_unchanged"]
            and result["rees46_exact_rows_after"] == 20692840
        )


if __name__ == "__main__":
    main()
