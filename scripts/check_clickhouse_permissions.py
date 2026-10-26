"""Read/write-scope probes; production INSERT probes select zero rows."""

import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ecommerce_analytics.ingestion.clickhouse import (  # noqa: E402
    MigrationError,
    configured_client,
    environment,
)

if __name__ == "__main__":
    values = environment()
    results = {}
    for role in ("INGEST", "DBT", "BI"):
        client = configured_client(values, role)
        rows = int(client.query("SELECT count(*) AS rows FROM ecommerce.raw_events")[0]["rows"])
        allowed = True
        try:
            client.command(
                "INSERT INTO ecommerce.raw_events SELECT * FROM ecommerce.raw_events LIMIT 0"
            )
        except MigrationError as exc:
            if "server code 497" not in str(exc):
                raise
            allowed = False
        if allowed != (role == "INGEST"):
            raise RuntimeError(f"Unexpected raw INSERT permission for {role}")
        results[role] = {"read_rows": rows, "raw_insert_allowed": allowed}
        if role == "DBT":
            name = "ecommerce_analytics.permission_probe_" + uuid4().hex
            client.command(f"CREATE VIEW {name} AS SELECT 1 AS ok")
            try:
                assert int(client.query(f"SELECT ok FROM {name}")[0]["ok"]) == 1
            finally:
                client.command(f"DROP VIEW {name}")
            results[role]["transformation_schema_view_create_select_drop"] = "passed"
    print(json.dumps(results, indent=2))
