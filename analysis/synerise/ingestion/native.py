"""Single-controller native file() historical load; no Python event transport."""

import argparse
import fcntl
import hashlib
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "architecture"))
from schema import COLUMNS, ddl  # noqa: E402

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment  # noqa: E402

ROOT = Path(__file__).resolve().parent
EXPECTED = dict(
    product_properties=1534050,
    product_buy=2318502,
    remove_from_cart=2688894,
    add_to_cart=7541117,
    search_query=13223769,
    page_visit=199451980,
)
MONTHS = [f"2022-{m:02}" for m in range(6, 13)]
SETTINGS = {
    "max_threads": "1",
    "max_insert_threads": "1",
    "max_memory_usage": str(512 * 1024**2),
    "max_bytes_before_external_group_by": str(64 * 1024**2),
    "max_bytes_before_external_sort": str(64 * 1024**2),
    "input_format_parallel_parsing": "0",
    "input_format_parquet_preserve_order": "1",
    "input_format_parquet_max_block_size": "10000",
    "max_block_size": "10000",
    "max_insert_block_size": "100000",
    "min_insert_block_size_rows": "100000",
    "min_insert_block_size_bytes": str(16 * 1024**2),
    "async_insert": "0",
    "insert_deduplicate": "0",
    "input_format_null_as_default": "0",
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(1024 * 1024):
            h.update(b)
    return h.hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def source_relation(source):
    if source not in COLUMNS:
        raise ValueError("Unknown source")
    types = ", ".join(f"`{n}` Nullable({kind})" for n, kind in COLUMNS[source])
    return f"file('synerise/e90b8fde/{source}.parquet','Parquet','{types}')"


def column_sql(source):
    return ",".join(f"`{n}`" for n, _ in COLUMNS[source])


def canonical_expression(source):
    """Version 2 encoding binds source, ordered column names/types and exact values."""
    header = (
        "synerise-row-v2:"
        + source
        + ":"
        + "".join(f"[{n}:{kind}]" for n, kind in COLUMNS[source])
        + "|"
    )
    fields = []
    for n, _kind in COLUMNS[source]:
        value = f"toString(`{n}`)"
        fields.append(f"if(isNull(`{n}`),'N',concat('V',toString(length({value})),':',{value}))")
    return f"concat('{header}'," + ",".join(fields) + ")"


def canonical_bytes(source, row):
    """Independent Python reference for targeted checksum encoding tests only."""
    header = (
        "synerise-row-v2:"
        + source
        + ":"
        + "".join(f"[{n}:{kind}]" for n, kind in COLUMNS[source])
        + "|"
    )
    out = header.encode()
    for n, _ in COLUMNS[source]:
        value = row[n]
        if value is None:
            out += b"N"
        else:
            raw = str(value).encode("utf-8")
            out += b"V" + str(len(raw)).encode() + b":" + raw
    return out


def aggregate_sql(source, relation, where=""):
    encoded = canonical_expression(source)
    md5 = f"MD5({encoded})"
    sha256 = f"SHA256({encoded})"
    fields = [
        "count() AS rows",
        f"sum(toUInt256(reinterpretAsUInt128({md5}))) AS md5_sum",
        f"sum(toUInt256(reinterpretAsUInt128(substring({sha256},1,16)))) AS sha256_sum",
        f"groupBitXor(reinterpretAsUInt64(substring({sha256},25,8))) AS sha256_xor",
    ]
    for n, kind in COLUMNS[source]:
        fields.append(f"countIf(isNull(`{n}`)) AS null_{n}")
        if kind == "Int64" or n == "timestamp":
            fields += [f"min(`{n}`) AS min_{n}", f"max(`{n}`) AS max_{n}"]
        else:
            fields += [
                f"min(length(`{n}`)) AS min_bytes_{n}",
                f"max(length(`{n}`)) AS max_bytes_{n}",
            ]
    return "SELECT " + ",".join(fields) + " FROM " + relation + (" WHERE " + where if where else "")


def combine_aggregates(partitions):
    """Associative sums/XOR, range extrema; no record-level groups or held row sets."""
    nonempty = [p for p in partitions if int(p["rows"])]
    if not nonempty:
        raise ValueError("Expected a nonempty source")
    combined = {}
    for key in nonempty[0]:
        values = [p[key] for p in nonempty]
        if key not in ("min_timestamp", "max_timestamp"):
            values = [int(v) for v in values]
        if key.startswith("min_"):
            combined[key] = min(values)
        elif key.startswith("max_"):
            combined[key] = max(values)
        elif key == "sha256_xor":
            combined[key] = 0
            for value in values:
                combined[key] ^= int(value)
        else:
            combined[key] = sum(int(v) for v in values)
    return combined


def validate_release(files):
    """No incomplete, unknown or incorrectly sized file can mark a release complete."""
    if set(files) != set(EXPECTED):
        raise ValueError("Exactly six expected files must be present")
    for source, count in EXPECTED.items():
        record = files[source]
        if (
            record.get("status") != "validated"
            or not record.get("source_hash_reverified")
            or int(record.get("destination_aggregate", {}).get("rows", -1)) != count
        ):
            raise ValueError("Incomplete or mismatched file: " + source)
    return sum(EXPECTED.values())


class Loader:
    def __init__(self):
        self.client = configured_client(environment(), "ADMIN")
        self.client.timeout = 3600
        self.release = str(uuid4())
        self.database = "synerise_raw__" + self.release.replace("-", "")
        self.comment = "synerise-native-" + self.release
        self.active = None
        self.stop = threading.Event()
        self.failure = None
        self.result = {
            "release_id": self.release,
            "database": self.database,
            "status": "private_incomplete",
            "clock_policy": "source-naive-civil-v1",
            "source_timezone_status": "unverified",
            "started_utc": datetime.now(UTC).isoformat(),
            "settings": SETTINGS,
            "checksum_policy": (
                "synerise-row-v2: MD5-128 sum and SHA256-prefix-128 "
                "sum in UInt256, SHA256-tail-64 XOR; little-endian hash integers"
            ),
            "files": {},
            "poc": [],
            "operations": [],
            "resource_samples": [],
        }
        self.manifest = json.loads(Path("analysis/synerise/download-manifest.json").read_text())
        self.hashes = {Path(x["name"]).stem: x["sha256"] for x in self.manifest["members"]}
        self.sql = []

    def save(self):
        atomic_json(ROOT / "results.json", self.result)
        (ROOT / "executed.sql").write_text(
            "-- Executed only against this task-owned release.\n" + ";\n\n".join(self.sql) + ";\n"
        )

    def query(self, sql):
        return json.loads(self.client._request(sql + " FORMAT JSON", parameters=SETTINGS))["data"]

    def resources(self):
        metrics = {
            x["metric"]: int(float(x["value"]))
            for x in self.query(
                "SELECT metric,value FROM system.asynchronous_metrics WHERE metric IN "
                "('MemoryResident','CGroupMemoryUsed','CGroupMemoryTotal')"
            )
        }
        metrics["tracked"] = int(
            self.query("SELECT value FROM system.metrics WHERE metric='MemoryTracking'")[0]["value"]
        )
        metrics["merges"] = int(self.query("SELECT count() AS n FROM system.merges")[0]["n"])
        metrics["free_disk"] = int(
            self.query("SELECT min(free_space) AS n FROM system.disks")[0]["n"]
        )
        metrics["parts"] = int(
            self.query(
                f"SELECT count() AS n FROM system.parts WHERE database='{self.database}' AND active"
            )[0]["n"]
        )
        metrics["time"] = time.time()
        return metrics

    def gate(self):
        for _ in range(30):
            m = self.resources()
            self.result["resource_samples"].append(m)
            if m["free_disk"] < 40 * 1024**3 or m["CGroupMemoryTotal"] != 8 * 1024**3:
                raise RuntimeError("Disk or container memory limit gate failed")
            if (
                m["tracked"] < 4 * 1024**3
                and m["CGroupMemoryUsed"] < 6 * 1024**3
                and m["merges"] <= 4
            ):
                return
            time.sleep(2)
        raise RuntimeError("Insufficient memory/merge headroom after bounded pause")

    def monitor(self):
        while not self.stop.wait(0.5):
            try:
                m = self.resources()
                self.result["resource_samples"].append(m)
                if (
                    m["tracked"] > 5 * 1024**3
                    or m["CGroupMemoryUsed"] > 6.5 * 1024**3
                    or m["free_disk"] < 40 * 1024**3
                ):
                    self.failure = "Resource stop: " + json.dumps(m)
                    active = self.active
                    if active:
                        self.client.command(f"KILL QUERY WHERE query_id='{active}' SYNC")
                    return
            except Exception as e:
                self.failure = "Monitoring failed: " + str(e)
                return

    def operation(self, sql, label, select=False):
        self.gate()
        if self.failure:
            raise RuntimeError(self.failure)
        query_id = "synerise_native_" + uuid4().hex
        self.active = query_id
        started = time.monotonic()
        self.sql.append(sql)
        self.save()
        item = {
            "label": label,
            "query_id": query_id,
            "started_unix": time.time(),
            "resources_before": self.resources(),
        }
        try:
            payload = self.client._request(
                sql + (" FORMAT JSON" if select else ""),
                parameters={**SETTINGS, "query_id": query_id},
            )
            if self.failure:
                raise RuntimeError(self.failure)
            item["success"] = True
            return json.loads(payload)["data"] if select else None
        except Exception as e:
            item["success"] = False
            item["error"] = str(e)
            raise
        finally:
            item["seconds"] = time.monotonic() - started
            item["resources_after"] = self.resources()
            self.result["operations"].append(item)
            self.active = None
            self.save()
            print(label, round(item["seconds"], 2), "s", item.get("success"), flush=True)

    def create(self, source, name):
        attempt = str(uuid4())
        sql = ddl(
            self.database,
            name,
            source,
            self.hashes[source],
            self.manifest["archive_sha256"],
            self.release,
            attempt,
        )
        self.client.command(sql, SETTINGS)
        self.sql.append(sql)
        identity = self.query(
            f"SELECT toString(uuid) AS uuid"
            f" FROM system.tables"
            f" WHERE database='{self.database}'"
            f" AND name='{name}'"
        )[0]["uuid"]
        return {
            "attempt_id": attempt,
            "table": name,
            "table_uuid": identity,
            "source_sha256": self.hashes[source],
            "status": "loading",
        }

    def drop_owned(self, record):
        name = record["table"]
        rows = self.query(
            f"SELECT toString(uuid) AS uuid,comment"
            f" FROM system.tables"
            f" WHERE database='{self.database}'"
            f" AND name='{name}'"
        )
        if not rows:
            return
        assert (
            rows[0]["uuid"] == record["table_uuid"]
            and rows[0]["comment"] == "synerise architecture isolated v1"
        )
        self.client.command(f"DROP TABLE {self.database}.{name} SYNC", SETTINGS)
        record["discarded"] = True

    def provenance(self, source, record):
        bad = (
            f"_source_file!='{source}.parquet' OR _source_sha256!='{self.hashes[source]}' "
            f"OR _archive_sha256!='{self.manifest['archive_sha256']}' "
            f"OR _release_id!=toUUID('{self.release}')"
            f" OR _attempt_id!=toUUID('{record['attempt_id']}')"
        )
        if source != "product_properties":
            bad += (
                " OR toString(source_day)!=substring(timestamp,1,10)"
                " OR tupleElement(event_time_source,2)!=("
                "toUInt32(substring(timestamp,12,2))*3600+"
                "toUInt32(substring(timestamp,15,2))*60+"
                "toUInt32(substring(timestamp,18,2)))"
            )
        value = self.operation(
            f"SELECT countIf({bad}) AS bad FROM {self.database}.{record['table']}",
            source + " provenance/clock",
            True,
        )
        assert int(value[0]["bad"]) == 0
        return value[0]

    def load(self, source):
        path = Path(f"data/external/synerise/source/{source}.parquet")
        assert sha(path) == self.hashes[source]
        record = self.create(source, "_attempt_" + source + "_" + uuid4().hex)
        self.result["files"][source] = record
        start = time.monotonic()
        sample_start = len(self.result["resource_samples"])
        record["started_utc"] = datetime.now(UTC).isoformat()
        relation = source_relation(source)
        # All rows assigned exactly once by their original timestamp month; no row pagination.
        partitions = [""] if source == "product_properties" else MONTHS
        try:
            schema = self.query("DESCRIBE TABLE " + relation)
            assert [(x["name"], x["type"]) for x in schema] == [
                (n, f"Nullable({k})") for n, k in COLUMNS[source]
            ]
            record["source_types"] = schema
            if source != "product_properties":
                bounds = self.operation(
                    f"SELECT min(timestamp) AS first,max(timestamp) AS last,"
                    f"countIf(isNull(timestamp)) AS nulls FROM {relation}",
                    source + " source bounds",
                    True,
                )[0]
                assert int(bounds["nulls"]) == 0
                assert (
                    "2022-06-01 00:00:00"
                    <= bounds["first"]
                    <= bounds["last"]
                    < "2023-01-01 00:00:00"
                )
                record["source_bounds"] = bounds
            record["chunks"] = []
            sources, destinations = [], []
            insert_seconds = 0.0
            reconciliation_seconds = 0.0
            destination = self.database + "." + record["table"]
            for month in partitions:
                where = f"substring(timestamp,1,7)='{month}'" if month else ""
                t = time.monotonic()
                src = self.operation(
                    aggregate_sql(source, relation, where),
                    source + " source checksum " + (month or "all"),
                    True,
                )[0]
                assert all(int(v) == 0 for k, v in src.items() if k.startswith("null_"))
                reconciliation_seconds += time.monotonic() - t
                sql = (
                    f"INSERT INTO {destination} ({column_sql(source)}) "
                    f"SELECT {column_sql(source)} FROM {relation}"
                    + (" WHERE " + where if where else "")
                )
                t = time.monotonic()
                self.operation(sql, source + " insert " + (month or "all"))
                insert_seconds += time.monotonic() - t
                t = time.monotonic()
                dst = self.operation(
                    aggregate_sql(source, destination, where),
                    source + " destination checksum " + (month or "all"),
                    True,
                )[0]
                assert src == dst, (source, month, "checksum/count/range/null mismatch")
                reconciliation_seconds += time.monotonic() - t
                sources.append(src)
                destinations.append(dst)
                record["chunks"].append(
                    {"month": month or "all", "source": src, "destination": dst}
                )
                self.save()
            total, actual = combine_aggregates(sources), combine_aggregates(destinations)
            assert total == actual and total["rows"] == EXPECTED[source]
            record["source_aggregate"], record["destination_aggregate"] = total, actual
            record["reconciliation_seconds"] = reconciliation_seconds
            record["provenance_clock"] = self.provenance(source, record)
            assert sha(path) == self.hashes[source]
            record["source_hash_reverified"] = True
            # One table rename only; query-ack loss is resolved by immutable UUID, never replayed.
            self.client.command(f"RENAME TABLE {destination} TO {self.database}.{source}", SETTINGS)
            record["table"] = source
            assert (
                self.query(
                    f"SELECT toString(uuid) AS uuid"
                    f" FROM system.tables"
                    f" WHERE database='{self.database}'"
                    f" AND name='{source}'"
                )[0]["uuid"]
                == record["table_uuid"]
            )
            record["status"] = "validated"
            record["errors"], record["retries"] = 0, 0
            record["finished_utc"] = datetime.now(UTC).isoformat()
            samples = self.result["resource_samples"][sample_start:]
            record["resources"] = {
                "sampled_peak_rss": max(x["MemoryResident"] for x in samples),
                "sampled_peak_cgroup": max(x["CGroupMemoryUsed"] for x in samples),
                "sampled_peak_tracked": max(x["tracked"] for x in samples),
                "maximum_merges": max(x["merges"] for x in samples),
                "maximum_release_parts": max(x["parts"] for x in samples),
                "minimum_free_disk": min(x["free_disk"] for x in samples),
            }
            record["insert_seconds"] = insert_seconds
            record["rows_per_insert_second"] = EXPECTED[source] / insert_seconds
            record["total_seconds"] = time.monotonic() - start
            record["storage"] = self.query(
                f"SELECT count() AS parts,"
                f"sum(rows) AS rows,"
                f"sum(bytes_on_disk) AS bytes_on_disk,"
                f"sum(data_compressed_bytes) AS compressed_bytes"
                f" FROM system.parts"
                f" WHERE database='{self.database}'"
                f" AND table='{source}'"
                f" AND active"
            )[0]
            atomic_json(ROOT / (source + "-validation.json"), record)
            self.save()
        except Exception as e:
            record["status"] = "failed_unpublished"
            record["errors"], record["retries"] = 1, 0
            record["error"] = str(e)
            self.save()
            # Resolve server completion before dropping a task-owned uncertain attempt.
            for item in self.result["operations"][-1:]:
                failed_id = item["query_id"]
                self.client.command(f"KILL QUERY WHERE query_id='{failed_id}' SYNC")
            self.drop_owned(record)
            self.save()
            raise

    def run(self):
        started = time.monotonic()
        db_uuid = None
        try:
            assert (
                sha(Path("data/external/synerise/synerise_dataset.tar.gz"))
                == self.manifest["archive_sha256"]
            )
            for source in EXPECTED:
                assert (
                    sha(Path(f"data/external/synerise/source/{source}.parquet"))
                    == self.hashes[source]
                )
            assert (
                int(
                    self.query(
                        "SELECT value"
                        " FROM system.server_settings"
                        " WHERE name='max_server_memory_usage'"
                    )[0]["value"]
                )
                == 6 * 1024**3
            )
            assert (
                int(self.query("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]) == 20692840
            )
            assert not self.query(
                "SELECT query_id FROM system.processes WHERE query_id!=currentQueryID()"
            )
            self.gate()
            self.client.command(
                f"CREATE DATABASE {self.database} ENGINE=Atomic COMMENT '{self.comment}'"
            )
            db_uuid = self.query(
                f"SELECT toString(uuid) AS uuid FROM system.databases WHERE name='{self.database}'"
            )[0]["uuid"]
            self.result["database_uuid"] = db_uuid
            self.save()
            thread = threading.Thread(target=self.monitor, daemon=True)
            thread.start()
            self.result["poc_reused"] = (
                "Six exact native POCs passed in history/2026-10-21-failed/results.json; "
                "unchanged source hashes and DDL"
            )
            self.save()
            for source in EXPECTED:
                self.load(source)
            assert validate_release(self.result["files"]) == 226758312
            self.result["status"] = "complete_validated_private"
            self.result["publication"] = (
                "Retained private; no BI/dbt grants or workflow changes. All six tables validated."
            )
            self.save()
            # Explicitly retaining a validated private release is an authorized completion state.
        except Exception as e:
            self.result["error"] = str(e)
            self.result["status"] = "stopped_private_incomplete"
            raise
        finally:
            self.stop.set()
            if "thread" in locals():
                thread.join(timeout=10)
            self.result["monitor_stop_reason"] = self.failure
            self.result["runtime_seconds"] = time.monotonic() - started
            self.result["finished_utc"] = datetime.now(UTC).isoformat()
            self.result["rees46_rows_after"] = int(
                self.query("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]
            )
            if db_uuid:
                self.result["database_retained"] = True
            self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-native-load", action="store_true")
    args = parser.parse_args()
    if not args.execute_native_load:
        parser.error("Explicit native historical load opt-in required")
    lockpath = Path("data/processed/synerise-native.lock")
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        Loader().run()


if __name__ == "__main__":
    main()
