"""Read completed-trial logs and exercise tiny isolated recovery cases after an abort."""

import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.ipc as ipc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guards import Attempt, publication_ready  # noqa: E402
from run import LIMITS, ROOT, Monitor  # noqa: E402
from schema import ddl  # noqa: E402

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment  # noqa: E402


def main():
    c = configured_client(environment(), "ADMIN")
    q = c.query
    result = json.loads((ROOT / "results.json").read_text())
    # Natural log flush has already elapsed; all queries constrained to benchmark prefix.
    logs = q(
        "SELECT query_id,type,exception_code,exception,memory_usage,written_rows,"
        "query_duration_ms,ProfileEvents['UserTimeMicroseconds'] AS cpu_user_us,"
        "ProfileEvents['SystemTimeMicroseconds'] AS cpu_system_us FROM system.query_log "
        "WHERE startsWith(query_id,'synerise_bench_') AND type!='QueryStart'"
    )
    by_id = {x["query_id"]: x for x in logs}
    for trial in result["trials"]:
        trial["query_logs"] = [by_id.get(b["query_id"]) for b in trial["batches"]]
    result["failures"] = [
        x for x in logs if int(x["exception_code"]) and int(x["exception_code"]) == 241
    ]
    result["decision"] = "INCONCLUSIVE"
    result["abort_reason"] = (
        "Global server tracker reached 6 GiB; "
        "no larger or repeated performance workload after warning"
    )
    # Tiny recovery trial only after conservative tracked-memory gate succeeds.
    with Monitor(q) as monitor:
        pass
    token = uuid4()
    db = "synerise_recovery_" + token.hex
    comment = "synerise-recovery-" + str(token)
    c.command(f"CREATE DATABASE {db} ENGINE=Atomic COMMENT '{comment}'")
    identity = q(f"SELECT toString(uuid) AS uuid FROM system.databases WHERE name='{db}'")[0][
        "uuid"
    ]
    digest = result["source_hashes"]["product_buy"]
    archive = json.loads(Path("analysis/synerise/download-manifest.json").read_text())[
        "archive_sha256"
    ]
    payload = pa.Table.from_pylist(
        [{"client_id": -1, "timestamp": "2022-08-01 00:00:00", "sku": -2}] * 20
    )
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, payload.schema) as writer:
        writer.write_table(payload)
    data = sink.getvalue().to_pybytes()
    recovery = {}
    try:
        uncertain = Attempt(digest)
        fresh = Attempt(digest)
        for name, attempt in [("uncertain", uncertain), ("fresh", fresh)]:
            c.command(ddl(db, name, "product_buy", digest, archive, str(token), attempt.identity))

        def send(name):
            c._request(
                f"INSERT INTO {db}.{name} (client_id,timestamp,sku) FORMAT ArrowStream",
                data,
                LIMITS,
            )

        def lose_ack():
            send("uncertain")
            raise ConnectionError("Simulated discard of successful acknowledgement")

        try:
            uncertain.execute(digest, lose_ack)
        except ConnectionError:
            pass
        refused = False
        try:
            uncertain.execute(digest, lambda: send("uncertain"))
        except RuntimeError:
            refused = True
        assert refused and uncertain.state == "uncertain"
        assert int(q(f"SELECT count() AS n FROM {db}.uncertain")[0]["n"]) == 20
        changed = Attempt(digest)
        try:
            changed.execute("0" * 64, lambda: send("fresh"))
        except ValueError:
            pass
        assert changed.state == "rejected"
        assert int(q(f"SELECT count() AS n FROM {db}.fresh")[0]["n"]) == 0
        fresh.execute(digest, lambda: send("fresh"))
        actual = q(f"SELECT client_id,timestamp,sku,count() AS n FROM {db}.fresh GROUP BY ALL")
        assert (
            len(actual) == 1 and int(actual[0]["client_id"]) == -1 and int(actual[0]["sku"]) == -2
        )
        assert actual[0]["timestamp"] == "2022-08-01 00:00:00" and int(actual[0]["n"]) == 20
        fresh.validate(True)
        assert not publication_ready({"product_buy": fresh}, result["source_hashes"])
        assert not publication_ready({"product_buy": uncertain}, ["product_buy"])
        recovery = {
            "same_attempt_reexecution_refused": True,
            "lost_ack_simulation": (
                "real committed 20-row insert followed by "
                "client-side ConnectionError; response discarded, not a network outage"
            ),
            "uncertain_attempt_rows": 20,
            "changed_checksum_rejected_before_insert": True,
            "fresh_attempt_rows": 20,
            "fresh_identity_distinct": fresh.identity != uncertain.identity,
            "fresh_exact_reconciliation": True,
            "incomplete_and_uncertain_publication_refused": True,
            "production_publication_exercised": False,
            "resource_samples": monitor.samples,
        }
        # Independent invalid date, HMS and shape cases (do not combine their failures).
        for stamp in ("2022-02-30 12:00:00", "2022-02-28 25:00:00", "2022-2-28 12:00:00"):
            failed = False
            try:
                c.command(
                    f"INSERT INTO {db}.fresh (client_id,timestamp,sku) VALUES (1,'{stamp}',1)",
                    LIMITS,
                )
            except Exception:
                failed = True
            assert failed
        recovery["separate_invalid_date_hms_shape_rejected"] = True
        assert int(q(f"SELECT count() AS n FROM {db}.fresh")[0]["n"]) == 20
    finally:
        owned = q(f"SELECT toString(uuid) AS uuid,comment FROM system.databases WHERE name='{db}'")
        assert owned[0]["uuid"] == identity and owned[0]["comment"] == comment
        c.command(f"DROP DATABASE {db} SYNC")
        recovery["cleanup_verified"] = not q(f"SELECT name FROM system.databases WHERE name='{db}'")
        result["recovery"] = recovery
        result["rees46_exact_rows_final"] = int(
            q("SELECT count() AS n FROM ecommerce.raw_events")[0]["n"]
        )
        result["final_server_tracked_memory"] = q(
            "SELECT value FROM system.metrics WHERE metric='MemoryTracking'"
        )
        result["finalized_unix_seconds"] = time.time()
        (ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(recovery, indent=2))


if __name__ == "__main__":
    main()
