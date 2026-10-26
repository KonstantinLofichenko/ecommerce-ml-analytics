"""Read-only preservation baseline before the explicitly authorized mount change."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment

ROOT = Path(__file__).parent


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(1024 * 1024):
            h.update(b)
    return h.hexdigest()


def snapshot():
    c = configured_client(environment(), "ADMIN")
    docker = json.loads(
        subprocess.check_output(["docker", "inspect", "ecommerce-ml-clickhouse-1"])
    )[0]
    paths = [
        Path(".env"),
        Path("infra/clickhouse/development.xml"),
        Path("data/processed/ecommerce.duckdb"),
        Path("data/external/synerise/synerise_dataset.tar.gz"),
    ]
    paths += list(Path("data/external/synerise/source").glob("*.parquet"))
    paths += [
        p
        for p in Path("dbt").rglob("*")
        if p.is_file() and not any(x in p.parts for x in ("target", "logs", "dbt_packages"))
    ]
    return {
        "file_hashes": {str(p): sha(p) for p in paths},
        "tables": c.query(
            "SELECT database,name,toString(uuid) AS uuid,create_table_query,total_rows"
            " FROM system.tables"
            " WHERE database IN ('ecommerce','ecommerce_analytics') ORDER BY database,name"
        ),
        "grants": c.query(
            "SELECT *"
            " FROM system.grants ORDER BY user_name,role_name,access_type,database,table,column"
        ),
        "volumes": [
            {k: m.get(k) for k in ("Name", "Destination", "RW")}
            for m in docker["Mounts"]
            if m["Type"] == "volume"
        ],
        "container_memory": docker["HostConfig"]["Memory"],
        "nanocpus": docker["HostConfig"]["NanoCpus"],
        "rees46_rows": int(c.query("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]),
        "other_ecommerce_containers": subprocess.check_output(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "label=com.docker.compose.project=ecommerce-ml",
                "--format",
                "{{.ID}} {{.Names}}",
            ]
        )
        .decode()
        .splitlines(),
    }


if __name__ == "__main__":
    c = configured_client(environment(), "ADMIN")
    for _ in range(12):
        work = c.query("SELECT query_id FROM system.processes WHERE query_id!=currentQueryID()")
        merges = c.query("SELECT database,table FROM system.merges")
        if not work and not merges:
            break
        time.sleep(2)
    assert not work and not merges, (work, merges)
    assert not c.query("SELECT database,table FROM system.mutations WHERE NOT is_done")
    before = snapshot()
    assert before["rees46_rows"] == 20692840 and before["container_memory"] == 8 * 1024**3
    # Private hash baseline includes .env: do not publish or print it.
    Path("/tmp/synerise-native-preservation.json").write_text(json.dumps(before))
    print("Idle safety gate passed; persistent volumes and protected files recorded privately.")
