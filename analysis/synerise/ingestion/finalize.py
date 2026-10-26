"""Read-only failure evidence and preservation checks; removes only an owned empty DB."""

import json
import subprocess
import time
from pathlib import Path

from native import ROOT, atomic_json
from preflight import snapshot

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment


def main():
    c = configured_client(environment(), "ADMIN")
    result = json.loads((ROOT / "results.json").read_text())
    before = json.loads(Path("/tmp/synerise-native-preservation.json").read_text())
    after = snapshot()
    checks = {
        key: before[key] == after[key]
        for key in (
            "file_hashes",
            "tables",
            "grants",
            "volumes",
            "container_memory",
            "nanocpus",
            "rees46_rows",
        )
    }

    def other(x):
        return sorted(
            line
            for line in x["other_ecommerce_containers"]
            if "ecommerce-ml-clickhouse-" not in line
        )

    checks["other_ecommerce_container_ids"] = other(before) == other(after)
    assert all(checks.values()), checks
    assert after["rees46_rows"] == 20692840
    result["preservation"] = checks
    result["protected_file_count"] = len(before["file_hashes"])
    result["archive_and_source_hashes_match_before_after"] = True
    ids = {x["query_id"] for x in result["operations"]}
    for _ in range(20):
        logs = c.query(
            "SELECT query_id,type,exception_code,exception,memory_usage,written_rows,"
            "query_duration_ms,ProfileEvents['UserTimeMicroseconds'] AS cpu_user_us,"
            "ProfileEvents['SystemTimeMicroseconds'] AS cpu_system_us FROM system.query_log "
            "WHERE startsWith(query_id,'synerise_native_') AND type!='QueryStart'"
        )
        result["query_logs"] = [row for row in logs if row["query_id"] in ids]
        if ids <= {row["query_id"] for row in result["query_logs"]}:
            break
        time.sleep(1)
    result["query_logs_complete"] = ids <= {row["query_id"] for row in result["query_logs"]}
    for source, record in result["files"].items():
        source_ids = {
            x["query_id"] for x in result["operations"] if x["label"].startswith(source + " ")
        }
        measured = [row for row in result["query_logs"] if row["query_id"] in source_ids]
        if measured:
            record["query_memory_peak"] = max(int(x["memory_usage"]) for x in measured)
            record["query_cpu_seconds"] = (
                sum(int(x["cpu_user_us"]) + int(x["cpu_system_us"]) for x in measured) / 1e6
            )
    counts = {}
    for source, record in result["files"].items():
        if record["status"] != "validated":
            continue
        counts[source] = int(
            c.query(f"SELECT count() AS n FROM {result['database']}.{source}")[0]["n"]
        )
        identity = c.query(
            f"SELECT toString(uuid) AS uuid FROM system.tables "
            f"WHERE database='{result['database']}' AND name='{source}'"
        )
        assert identity[0]["uuid"] == record["table_uuid"]
        assert counts[source] == int(record["destination_aggregate"]["rows"])
    result["validated_destination_counts"] = counts
    result["retained_total_rows"] = sum(counts.values())
    result["retained_event_rows"] = sum(n for s, n in counts.items() if s != "product_properties")
    assert not c.query(
        f"SELECT name FROM system.tables WHERE database='{result['database']}' "
        "AND startsWith(name,'_attempt_')"
    )
    if result["status"] == "complete_validated_private":
        assert result["retained_total_rows"] == 226758312
        assert result["retained_event_rows"] == 225224262
    failed = [row for row in result["query_logs"] if int(row["exception_code"])]
    result["server_errors"] = failed
    result["publication"] = (
        "Private; incomplete release is not published and no consumer grants changed"
        if result["status"] != "complete_validated_private"
        else "Complete validated private release; pointer not published"
    )
    db = result["database"]
    owned = c.query(
        f"SELECT toString(uuid) AS uuid,comment FROM system.databases WHERE name='{db}'"
    )
    if owned:
        assert owned[0]["uuid"] == result["database_uuid"]
        assert owned[0]["comment"] == "synerise-native-" + result["release_id"]
        tables = c.query(
            f"SELECT name,toString(uuid) AS uuid FROM system.tables WHERE database='{db}'"
        )
        if result["status"] == "stopped_private_incomplete" and not tables:
            c.command(f"DROP DATABASE {db} SYNC")
            result["empty_failed_database_removed"] = True
            result["database_retained"] = False
    result["release_databases_remaining"] = c.query(
        f"SELECT name FROM system.databases WHERE name='{db}'"
    )
    docker = json.loads(
        subprocess.check_output(["docker", "inspect", "ecommerce-ml-clickhouse-1"])
    )[0]
    result["final_runtime"] = {
        "health": docker["State"]["Health"]["Status"],
        "memory_bytes": docker["HostConfig"]["Memory"],
        "nanocpus": docker["HostConfig"]["NanoCpus"],
        "mounts": [
            {k: m.get(k) for k in ("Type", "Name", "Source", "Destination", "RW")}
            for m in docker["Mounts"]
        ],
        "server_limit": c.query(
            "SELECT value FROM system.server_settings WHERE name='max_server_memory_usage'"
        ),
        "memory": c.query(
            "SELECT metric,value FROM system.asynchronous_metrics WHERE metric IN "
            "('MemoryResident','CGroupMemoryUsed','CGroupMemoryTotal')"
        ),
        "tracked": c.query("SELECT value FROM system.metrics WHERE metric='MemoryTracking'"),
        "active_queries": c.query(
            "SELECT query_id,user FROM system.processes WHERE query_id!=currentQueryID()"
        ),
        "raw": c.query(
            "SELECT toString(uuid) AS uuid,total_rows FROM system.tables "
            "WHERE database='ecommerce' AND name='raw_events'"
        ),
        "source_mount_read_only": any(
            m["Destination"] == "/var/lib/clickhouse/user_files/synerise/e90b8fde" and not m["RW"]
            for m in docker["Mounts"]
        ),
    }
    assert result["final_runtime"]["health"] == "healthy"
    assert result["final_runtime"]["source_mount_read_only"]
    atomic_json(ROOT / "results.json", result)
    for source, record in result["files"].items():
        atomic_json(ROOT / (source + "-validation.json"), record)
    print(
        json.dumps(
            {
                "preservation": checks,
                "errors": failed,
                "empty_failed_database_removed": result.get("empty_failed_database_removed"),
                "health": result["final_runtime"]["health"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
