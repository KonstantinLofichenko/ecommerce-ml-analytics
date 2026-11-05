"""Frozen artifact export and opt-in isolated manifest-publication recovery checks."""

import gzip
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment, identifier
from ecommerce_analytics.reporting.ml_results import (
    FEATURES,
    NOTEBOOK,
    SCRIPTED,
    canonical,
    compatible_models,
    metric_record,
    notebook_records,
    probabilities_checked,
    row_hashes,
    saved_records,
    validate_package,
)
from ecommerce_analytics.reporting.publication import publish

ARTIFACTS = Path("data/processed/phase-4.1/initial-2026-10-30")


def make_package(path, records=None):
    path.mkdir()
    row = {
        "experiment_id": SCRIPTED,
        "model_name": "lightgbm",
        "model_version": "fixture",
        "dataset_split": "validation",
        "provenance": "artifact_inference",
        "client_id": -2,
        "first_purchase_ts": "2022-09-15T00:00:00+00:00",
        "actual_target": 1,
        "prediction_probability": 0.25,
    }
    records = records or [
        ("predictions", row),
        (
            "metrics",
            metric_record(
                SCRIPTED,
                "lightgbm",
                "fixture",
                "validation",
                "average_precision",
                0.2,
                "original_scripted_metrics_json",
                "stored_full_precision",
            ),
        ),
    ]
    if records[0][0] == "predictions" and len(records) == 2:
        records = records + [
            (
                "importance",
                {
                    "experiment_id": SCRIPTED,
                    "model_name": "lightgbm",
                    "model_version": "fixture",
                    "dataset_split": "train",
                    "provenance": "saved",
                    "feature_name": FEATURES[0],
                    "importance_method": "gain",
                    "importance_value": 2.0,
                },
            ),
            *[
                (
                    "calibration",
                    {
                        "experiment_id": SCRIPTED,
                        "model_name": "lightgbm",
                        "model_version": "fixture",
                        "dataset_split": "validation",
                        "provenance": "saved",
                        "probability_bin_lower": lower,
                        "probability_bin_upper": upper,
                        "customer_count": n,
                        "mean_predicted_probability": mean,
                        "observed_positive_rate": rate,
                    },
                )
                for lower, upper, n, mean, rate in [
                    (0.0, 0.5, 1, 0.25, 1.0),
                    (0.5, 1.0, 0, None, None),
                ]
            ],
        ]
    counts, sums, digest = {}, [0, 0], hashlib.sha256()
    with gzip.open(path / "rows.jsonl.gz", "wt") as handle:
        for kind, value in records:
            payload = canonical(value)
            line = canonical({"record_type": kind, "payload": payload}) + "\n"
            handle.write(line)
            digest.update(line.encode())
            counts[kind] = counts.get(kind, 0) + 1
            a, b = row_hashes(kind, payload)
            sums[0] += a
            sums[1] += b
    meta = {
        "export_id": "fixture-" + uuid4().hex,
        "counts": counts,
        "checksums": list(map(str, sums)),
        "bundle_digest": digest.hexdigest(),
        "scored_at": "2026-11-05T00:00:00+00:00",
    }
    (path / "package.json").write_text(json.dumps(meta))
    return meta, records


@pytest.mark.parametrize("values,n", [([0, 0.5, 1], 3), ([], 0)])
def test_probabilities_valid(values, n):
    assert len(probabilities_checked(values, n)) == n


@pytest.mark.parametrize(
    "values,n", [([np.nan], 1), ([np.inf], 1), ([-0.1], 1), ([1.1], 1), ([0], 2), ([[0]], 1)]
)
def test_probabilities_invalid(values, n):
    with pytest.raises(ValueError):
        probabilities_checked(values, n)


@pytest.mark.parametrize("value", [np.nan, np.inf, True, "0.2"])
def test_metrics_reject_invalid(value):
    with pytest.raises(ValueError):
        metric_record(SCRIPTED, "dummy", "x", "test", "brier", value, "saved", "full")


def test_package_corruption_and_duplicates(tmp_path):
    path = tmp_path / "package"
    meta, records = make_package(path)
    assert validate_package(path) == meta
    with gzip.open(path / "rows.jsonl.gz", "at") as handle:
        handle.write(
            canonical({"record_type": "metrics", "payload": canonical(records[1][1])}) + "\n"
        )
    with pytest.raises(ValueError, match="Duplicate"):
        validate_package(path)


def test_notebook_cannot_supply_predictions(tmp_path):
    _, records = make_package(tmp_path / "initial")
    records[0][1]["experiment_id"] = NOTEBOOK
    make_package(tmp_path / "invalid", records)
    with pytest.raises(ValueError, match="Only scripted"):
        validate_package(tmp_path / "invalid")


def test_package_manifest_tampering(tmp_path):
    path = tmp_path / "package"
    meta, _ = make_package(path)
    meta["checksums"][0] = "0"
    (path / "package.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="checksums"):
        validate_package(path)


def test_recorded_evidence_and_no_notebook_calibration():
    rows = list(notebook_records(Path("notebooks/01_repeat_purchase_exploration.ipynb")))
    assert len(rows) == 30
    assert {kind for kind, _ in rows} == {"metrics", "importance"}
    assert all(row["experiment_id"] == NOTEBOOK for _, row in rows)


def test_saved_calibration_count_guard():
    report = {
        "evaluations": {"validation": {"dummy": {"metrics": {}, "calibration": [{"rows": 2}]}}},
        "splits": {"validation": {"customers": 1}},
    }
    with pytest.raises(ValueError, match="calibration counts"):
        list(saved_records(report, dict.fromkeys(("dummy", "logistic", "lightgbm"), "fixture")))


def test_compatibility_fails_before_loading(monkeypatch):
    report = {"versions": {"numpy": "0.0.0"}, "selection": {}}
    monkeypatch.setattr("joblib.load", lambda _: pytest.fail("must reject before unpickling"))
    with pytest.raises(ValueError, match="Dependency mismatch"):
        compatible_models(ARTIFACTS, report, report["selection"])


def test_feature_order_guard(monkeypatch):
    report = {"versions": {}, "features": FEATURES[::-1], "selection": {}}
    monkeypatch.setattr("joblib.load", lambda _: pytest.fail("must reject before unpickling"))
    with pytest.raises(ValueError, match="Feature order"):
        compatible_models(ARTIFACTS, report, report["selection"])


@pytest.fixture
def live_database():
    if os.environ.get("ECOMMERCE_ML_REPORTING_TESTS") != "1":
        pytest.skip("Explicit opt-in required for UUID-owned isolated integration database")
    client = configured_client(environment(), "ADMIN")
    name = "ml_reporting_test_" + uuid4().hex
    client.command(f"CREATE DATABASE {identifier(name)} COMMENT 'ml-reporting-test-owned'")
    identity = client.query(f"SELECT uuid FROM system.databases WHERE name='{name}'")[0]["uuid"]
    try:
        yield client, name
    finally:
        current = client.query(f"SELECT uuid,comment FROM system.databases WHERE name='{name}'")
        assert current[0] == {"uuid": identity, "comment": "ml-reporting-test-owned"}
        client.command(f"DROP DATABASE {identifier(name)} SYNC")


class FaultClient:
    def __init__(self, client, failure):
        self.client, self.failure, self.fired = client, failure, False

    def __getattr__(self, name):
        return getattr(self.client, name)

    def insert(self, table, payload):
        target = "_ml_export_publications" if self.failure == "manifest_ack" else "_ml_export_rows"
        if not self.fired and table.endswith(target):
            self.fired = True
            if self.failure == "corruption":
                data = [json.loads(line) for line in payload.splitlines()]
                row = json.loads(data[0]["payload"])
                row["prediction_probability"] = 0.99
                data[0]["payload"] = canonical(row)
                self.client.insert(table, ("\n".join(map(canonical, data)) + "\n").encode())
                return
            self.client.insert(table, payload)
            raise RuntimeError("simulated committed INSERT with lost acknowledgement")
        return self.client.insert(table, payload)


def test_live_publish_views_noop(live_database, tmp_path):
    client, db = live_database
    path = tmp_path / "package"
    make_package(path)
    assert publish(client, db, path)["status"] == "published"
    assert publish(client, db, path)["status"] == "validated_noop"
    assert client.query(f"SELECT count() n FROM {db}.ml_customer_predictions")[0]["n"] == 1
    row = client.query(
        f"SELECT client_id,prediction_probability,scored_at FROM {db}.ml_customer_predictions"
    )[0]
    assert row == {
        "client_id": -2,
        "prediction_probability": 0.25,
        "scored_at": "2026-11-05T00:00:00+00:00",
    }
    assert client.query(f"SELECT count() n FROM {db}.ml_experiment_metrics")[0]["n"] == 1
    assert client.query(f"SELECT count() n FROM {db}.ml_feature_importance")[0]["n"] == 1
    assert client.query(f"SELECT count() n FROM {db}.ml_calibration")[0]["n"] == 2
    empty = client.query(
        f"SELECT mean_predicted_probability,observed_positive_rate "
        f"FROM {db}.ml_calibration WHERE customer_count=0"
    )[0]
    assert empty == {"mean_predicted_probability": None, "observed_positive_rate": None}


@pytest.mark.parametrize("failure", ["rows_ack", "corruption", "manifest_ack"])
def test_live_recovery(live_database, tmp_path, failure):
    client, db = live_database
    path = tmp_path / "package"
    make_package(path)
    wrapper = FaultClient(client, failure)
    if failure == "manifest_ack":
        assert publish(wrapper, db, path)["status"] == "published"
    else:
        with pytest.raises((RuntimeError, ValueError)):
            publish(wrapper, db, path)
        assert client.query(f"SELECT count() n FROM {db}.ml_customer_predictions")[0]["n"] == 0
        assert publish(client, db, path)["status"] == "published"
    assert publish(client, db, path)["status"] == "validated_noop"
    assert client.query(f"SELECT count() n FROM {db}.ml_customer_predictions")[0]["n"] == 1


def test_live_unmanaged_collision(live_database, tmp_path):
    client, db = live_database
    client.command(f"CREATE TABLE {db}.ml_customer_predictions (x Int64) ENGINE=Memory")
    path = tmp_path / "package"
    make_package(path)
    with pytest.raises(ValueError, match="Unmanaged"):
        publish(client, db, path)
    assert client.query(f"SELECT count() n FROM system.tables WHERE database='{db}'")[0]["n"] == 1


def test_live_managed_schema_tampering(live_database, tmp_path):
    client, db = live_database
    path = tmp_path / "package"
    make_package(path)
    publish(client, db, path)
    client.command(f"ALTER TABLE {db}._ml_export_rows ADD COLUMN unexpected String")
    with pytest.raises(ValueError, match="DDL differs"):
        publish(client, db, path)


def test_live_conflicting_bundle_is_refused(live_database, tmp_path):
    client, db = live_database
    first = tmp_path / "first"
    meta, records = make_package(first)
    publish(client, db, first)
    records[1][1]["metric_value"] = 0.3
    second = tmp_path / "second"
    other, _ = make_package(second, records)
    other["export_id"] = meta["export_id"]
    (second / "package.json").write_text(json.dumps(other))
    with pytest.raises(ValueError, match="Conflicting"):
        publish(client, db, second)
    result = client.query(f"SELECT metric_value FROM {db}.ml_experiment_metrics")[0]
    assert result["metric_value"] == 0.2
