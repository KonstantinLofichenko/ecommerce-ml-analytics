"""One-time native Parquet bulk import into synerise_raw; count-only validation."""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "architecture"))
from schema import COLUMNS  # noqa: E402

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment  # noqa: E402

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "product_properties": 1534050,
    "product_buy": 2318502,
    "remove_from_cart": 2688894,
    "add_to_cart": 7541117,
    "search_query": 13223769,
    "page_visit": 199451980,
}
# Query-local cap uses available resources while retaining the 6 GiB server limit.
OPTIONS = {
    "max_threads": "2",
    "max_memory_usage": str(4 * 1024**3),
    "async_insert": "0",
    "insert_deduplicate": "0",
    "input_format_null_as_default": "0",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        parser.error("Explicit --execute required for the one-time bulk load")
    client = configured_client(environment(), "ADMIN")
    client.timeout = 3600

    def query(sql):
        return json.loads(client._request(sql + " FORMAT JSON", parameters=OPTIONS))["data"]

    def protected_tables():
        return query(
            "SELECT database,name,toString(uuid) AS uuid,create_table_query,total_rows "
            "FROM system.tables WHERE database IN "
            "('ecommerce','ecommerce_analytics',"
            "'synerise_raw__8efbe3d95dfc431cb1fa66f980f13a67') "
            "ORDER BY database,name"
        )

    # No CREATE or INSERT if the destination contains existing tables/data.
    tables = query("SELECT name FROM system.tables WHERE database='synerise_raw'")
    if tables:
        raise RuntimeError("synerise_raw already contains tables; stopped without writing")
    assert int(query("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]) == 20692840
    before = protected_tables()
    assert not query("SELECT query_id FROM system.processes WHERE query_id!=currentQueryID()")
    assert (
        int(
            query("SELECT value FROM system.server_settings WHERE name='max_server_memory_usage'")[
                0
            ]["value"]
        )
        == 6 * 1024**3
    )
    for source in EXPECTED:
        assert Path(f"data/external/synerise/source/{source}.parquet").is_file()
    result = {
        "started_utc": datetime.now(UTC).isoformat(),
        "database": "synerise_raw",
        "status": "loading",
        "options": OPTIONS,
        "tables": {},
        "errors": [],
    }
    sql_audit = []
    started = time.monotonic()

    def save():
        (ROOT / "bulk-results.json").write_text(json.dumps(result, indent=2) + "\n")
        (ROOT / "bulk-executed.sql").write_text(
            "-- One-time audit only: do not replay INSERTs into loaded tables.\n"
            + ";\n\n".join(sql_audit)
            + ";\n"
        )

    try:
        client.command("CREATE DATABASE IF NOT EXISTS synerise_raw ENGINE=Atomic", OPTIONS)
        sql_audit.append("CREATE DATABASE IF NOT EXISTS synerise_raw ENGINE=Atomic")
        for source, expected in EXPECTED.items():
            fields = COLUMNS[source]
            structure = ", ".join(f"`{n}` {kind}" for n, kind in fields)
            cols = ", ".join(f"`{n}`" for n, _ in fields)
            if source == "product_properties":
                key = "`sku`"
            else:
                key = "`client_id`, `timestamp`"
                if source != "search_query":
                    key += ", `url`" if source == "page_visit" else ", `sku`"
            ddl = (
                f"CREATE TABLE synerise_raw.{source} ({structure}) "
                f"ENGINE=MergeTree ORDER BY ({key})"
            )
            client.command(ddl, OPTIONS)
            sql_audit.append(ddl)
            query_id = "synerise_bulk_" + uuid4().hex
            record = {"expected_rows": expected, "status": "inserting", "query_id": query_id}
            result["tables"][source] = record
            insert = (
                f"INSERT INTO synerise_raw.{source} ({cols}) SELECT {cols} "
                f"FROM file('synerise/e90b8fde/{source}.parquet','Parquet','{structure}')"
            )
            sql_audit.append(insert)
            save()
            t = time.monotonic()
            client.command(insert, {**OPTIONS, "query_id": query_id})
            record["insert_seconds"] = time.monotonic() - t
            count_sql = f"SELECT count() AS n FROM synerise_raw.{source}"
            count = int(query(count_sql)[0]["n"])
            sql_audit.append(count_sql)
            record["rows"] = count
            if count != expected:
                raise RuntimeError(f"{source}: expected {expected} rows, observed {count}")
            record["status"] = "count_validated"
            save()
            print(source, count, f"{record['insert_seconds']:.3f}s", flush=True)
        result["total_rows"] = sum(r["rows"] for r in result["tables"].values())
        result["event_rows"] = sum(
            r["rows"] for s, r in result["tables"].items() if s != "product_properties"
        )
        assert result["total_rows"] == 226758312 and result["event_rows"] == 225224262
        result["status"] = "complete"
    except Exception as error:
        result["status"] = "stopped"
        result["errors"].append(str(error))
        # No retry, rebuild or DROP; preserve partial state for explicit inspection.
        raise
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        result["finished_utc"] = datetime.now(UTC).isoformat()
        result["rees46_rows_after"] = int(
            query("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]
        )
        result["protected_tables_unchanged"] = protected_tables() == before
        result["previous_private_database_preserved"] = True
        save()
        assert result["rees46_rows_after"] == 20692840 and result["protected_tables_unchanged"]


if __name__ == "__main__":
    main()
