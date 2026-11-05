"""Manifest-gated publication. Uncommitted attempts are never visible to consumers."""

import fcntl
import gzip
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from ecommerce_analytics.ingestion.clickhouse import identifier
from ecommerce_analytics.reporting.ml_results import canonical, validate_package

MARKER = "managed:ml-reporting-v1"
VIEWS = {
    "ml_customer_predictions": (
        "predictions",
        {
            "client_id": "Int",
            "first_purchase_ts": "String",
            "prediction_probability": "Float",
            "actual_target": "Int",
            "scored_at": "String",
        },
    ),
    "ml_experiment_metrics": (
        "metrics",
        {
            "metric_name": "String",
            "metric_value": "Float",
            "value_precision": "String",
            "evaluated_at": "Nullable(String)",
        },
    ),
    "ml_feature_importance": (
        "importance",
        {
            "feature_name": "String",
            "importance_method": "String",
            "importance_value": "Float",
        },
    ),
    "ml_calibration": (
        "calibration",
        {
            "probability_bin_lower": "Float",
            "probability_bin_upper": "Float",
            "customer_count": "Int",
            "mean_predicted_probability": "Nullable(Float64)",
            "observed_positive_rate": "Nullable(Float64)",
        },
    ),
}
COMMON = ("experiment_id", "model_name", "model_version", "dataset_split", "provenance")


def literal(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def definitions(database):
    db = identifier(database)
    rows = f"{db}._ml_export_rows"
    publications = f"{db}._ml_export_publications"
    result = {
        "_ml_export_rows": f"CREATE TABLE {rows} (export_id String, attempt_id String, "
        "record_type LowCardinality(String), payload String) ENGINE=MergeTree "
        f"ORDER BY (export_id, attempt_id, record_type) COMMENT '{MARKER}'",
        "_ml_export_publications": f"CREATE TABLE {publications} (export_id String, "
        "attempt_id String, bundle_digest String, metadata String, "
        "published_at DateTime64(6, 'UTC') DEFAULT now64(6)) ENGINE=MergeTree "
        f"ORDER BY export_id COMMENT '{MARKER}'",
    }
    for name, (kind, columns) in VIEWS.items():
        expressions = ["r.export_id", "r.attempt_id"]
        for col, dtype in {**dict.fromkeys(COMMON, "String"), **columns}.items():
            expression = (
                f"JSONExtract(r.payload, '{col}', '{dtype}')"
                if dtype.startswith("Nullable")
                else f"JSONExtract{dtype}(r.payload, '{col}')"
            )
            if col == "scored_at":
                expression = "JSONExtractString(p.metadata, 'scored_at')"
            expressions.append(f"{expression} AS {identifier(col)}")
        types = {"String": "String", "Int": "Int64", "Float": "Float64"}
        fields = {
            "export_id": "String",
            "attempt_id": "String",
            **dict.fromkeys(COMMON, "String"),
            **columns,
        }
        schema = ", ".join(f"{identifier(k)} {types.get(v, v)}" for k, v in fields.items())
        result[name] = (
            f"CREATE VIEW {db}.{identifier(name)} ({schema}) "
            f"COMMENT '{MARKER}' AS SELECT {', '.join(expressions)} FROM {rows} r "
            f"INNER JOIN {publications} p ON r.export_id=p.export_id "
            f"AND r.attempt_id=p.attempt_id WHERE r.record_type='{kind}'"
        )
    return result


def bootstrap(client, database):
    """Do not create databases or replace pre-existing unmanaged objects."""
    expected = definitions(database)
    # Preflight all collisions before any mutation; compare canonical server DDL on reruns.
    existing = client.query(
        "SELECT name, comment, create_table_query FROM system.tables "
        f"WHERE database={literal(database)}"
    )
    for row in existing:
        if row["name"] in expected and not row["comment"].startswith(MARKER + ";definition:"):
            raise ValueError(f"Unmanaged reporting namespace collision: {row['name']}")
    for name, sql in expected.items():
        found = next((r for r in existing if r["name"] == name), None)
        if found:
            signature = hashlib.sha256(sql.encode()).hexdigest()
            expected_sql = sql.replace(
                f"COMMENT '{MARKER}'", f"COMMENT '{MARKER};definition:{signature}'"
            )
            normalized = client.query(
                f"SELECT formatQuerySingleLine({literal(expected_sql)}) AS expected, "
                f"formatQuerySingleLine({literal(found['create_table_query'])}) AS actual"
            )[0]
            # Server appends index_granularity to MergeTree definitions.
            actual = normalized["actual"].replace(" SETTINGS index_granularity = 8192", "")
            if actual != normalized["expected"]:
                raise ValueError(f"Actual managed reporting DDL differs: {name}")
    for name, sql in expected.items():
        found = next((r for r in existing if r["name"] == name), None)
        if found:
            # Stored DDL hash guards against changes, including view extraction/provenance.
            signature = hashlib.sha256(sql.encode()).hexdigest()
            if f"definition:{signature}" not in found["comment"]:
                raise ValueError(f"Managed reporting schema differs: {name}")
        else:
            signature = hashlib.sha256(sql.encode()).hexdigest()
            client.command(
                sql.replace(f"COMMENT '{MARKER}'", f"COMMENT '{MARKER};definition:{signature}'")
            )


def committed(client, database, meta):
    records = client.query(
        f"SELECT attempt_id,bundle_digest FROM {identifier(database)}."
        f"_ml_export_publications WHERE export_id={literal(meta['export_id'])}"
    )
    if not records:
        return None
    if len(records) != 1 or records[0]["bundle_digest"] != meta["bundle_digest"]:
        raise ValueError("Conflicting or duplicate publication manifest")
    verify_attempt(client, database, meta, records[0]["attempt_id"])
    return records[0]["attempt_id"]


def verify_attempt(client, database, meta, attempt):
    rows = client.query(
        "SELECT record_type,count() AS n, "
        "toString(sum(toUInt256(reinterpretAsUInt128("
        "MD5(concat(record_type,':',payload)))))) AS md5, "
        "toString(sum(toUInt256(reinterpretAsUInt128("
        "substring(SHA256(concat(record_type,':',payload)),1,16))))) AS sha "
        f"FROM {identifier(database)}._ml_export_rows "
        f"WHERE export_id={literal(meta['export_id'])} AND attempt_id={literal(attempt)} "
        "GROUP BY record_type"
    )
    counts = {r["record_type"]: int(r["n"]) for r in rows}
    hashes = [str(sum(int(r[key]) for r in rows)) for key in ("md5", "sha")]
    if counts != meta["counts"] or hashes != meta["checksums"]:
        raise ValueError("Staged reporting count/checksum mismatch; publication refused")


def publish(client, database, package):
    """Single-host writer only. No uncertain INSERT is retried; rerun creates a fresh attempt."""
    package = Path(package)
    meta = validate_package(package)
    # Lock beside the package is insufficient across packages; one global local writer lock.
    with Path("/tmp/ecommerce-ml-reporting-publication.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        bootstrap(client, database)
        attempt = committed(client, database, meta)
        if attempt:
            return {
                "status": "validated_noop",
                "export_id": meta["export_id"],
                "attempt_id": attempt,
            }
        attempt = uuid4().hex
        batch = []
        with gzip.open(package / "rows.jsonl.gz", "rt") as handle:
            for line in handle:
                batch.append(
                    canonical(
                        {**json.loads(line), "export_id": meta["export_id"], "attempt_id": attempt}
                    )
                )
                if len(batch) >= 5000:
                    client.insert(
                        f"{identifier(database)}._ml_export_rows",
                        ("\n".join(batch) + "\n").encode(),
                    )
                    batch.clear()
            if batch:
                client.insert(
                    f"{identifier(database)}._ml_export_rows", ("\n".join(batch) + "\n").encode()
                )
        verify_attempt(client, database, meta, attempt)
        manifest = canonical(
            {
                "export_id": meta["export_id"],
                "attempt_id": attempt,
                "bundle_digest": meta["bundle_digest"],
                "metadata": canonical(meta),
            }
        )
        try:
            client.insert(
                f"{identifier(database)}._ml_export_publications", (manifest + "\n").encode()
            )
        except Exception:
            # Resolve a lost acknowledgement by reading, never repeating the manifest INSERT.
            if committed(client, database, meta) != attempt:
                raise
        if committed(client, database, meta) != attempt:
            raise ValueError("Publication acknowledgement could not be resolved")
        return {"status": "published", "export_id": meta["export_id"], "attempt_id": attempt}
