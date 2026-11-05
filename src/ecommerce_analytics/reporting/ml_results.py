"""Prepare provenance-separated reporting data from trusted frozen artifacts; never fit."""

import gzip
import hashlib
import importlib.metadata
import json
import math
import platform
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np

from ecommerce_analytics.models.repeat_purchase import FEATURES, chronological_split, load_dataset

SCRIPTED = "v4.1-scripted-2026-10-30"
NOTEBOOK = "v4.1-notebook-preserved"
NOTEBOOK_SHA = "56c1ddbde7b35b8e858adaf2718d4bdc0ec288e988e073819bd17b0c0aa06378"
MODELS = ("dummy", "logistic", "lightgbm")
KINDS = ("predictions", "metrics", "importance", "calibration")
POLICY = "ml-reporting-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def file_hash(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def row_hashes(kind, payload):
    raw = (kind + ":" + payload).encode()
    return (
        int.from_bytes(hashlib.md5(raw).digest(), "little"),
        int.from_bytes(hashlib.sha256(raw).digest()[:16], "little"),
    )


def probabilities_checked(probabilities, expected):
    values = np.asarray(probabilities, dtype=float)
    if values.shape != (expected,) or not np.isfinite(values).all():
        raise ValueError("Prediction length/finite-value mismatch")
    if ((values < 0) | (values > 1)).any():
        raise ValueError("Probabilities must be within [0, 1]")
    return values


def metric_record(experiment, model, version, split, name, value, provenance, precision):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Metrics must be finite numeric scalars")
    return {
        "experiment_id": experiment,
        "model_name": model,
        "model_version": version,
        "dataset_split": split,
        "metric_name": name,
        "metric_value": value,
        "provenance": provenance,
        "value_precision": precision,
        "evaluated_at": None,
    }


def compatible_models(artifacts, report, selection):
    """Fail before unpickling on runtime mismatch; load only explicitly trusted local artifacts."""
    mismatches = {
        package: {"expected": version, "actual": importlib.metadata.version(package)}
        for package, version in report["versions"].items()
        if importlib.metadata.version(package) != version
    }
    if mismatches:
        raise ValueError("Dependency mismatch: " + canonical(mismatches))
    if report["features"] != FEATURES or report["selection"] != selection:
        raise ValueError("Feature order or historical selection metadata mismatch")
    expected_rows = {"train": 122467, "validation": 78700, "test": 33020}
    if any(report["splits"][s]["customers"] != n for s, n in expected_rows.items()):
        raise ValueError("Unexpected recorded split counts")
    models, hashes = {}, {}
    for name in MODELS:
        path = artifacts / f"{name}.joblib"
        hashes[name] = file_hash(path)
        model = joblib.load(path)
        if list(model.feature_names_in_) != FEATURES or list(model.classes_) != [0, 1]:
            raise ValueError(f"Model feature/class mismatch: {name}")
        if model.n_features_in_ != 7:
            raise ValueError("Unexpected model width")
        models[name] = model
    prior = report["splits"]["train"]["prevalence"]
    if models["dummy"].strategy != "prior" or not np.isclose(
        models["dummy"].class_prior_[1], prior
    ):
        raise ValueError("Dummy prior mismatch")
    pipeline = models["logistic"]
    if list(pipeline.named_steps) != ["log1p", "scale", "classifier"]:
        raise ValueError("Unexpected preprocessing pipeline")
    if pipeline.named_steps["log1p"].func is not np.log1p:
        raise ValueError("Unexpected feature transform")
    if int(pipeline.named_steps["scale"].n_samples_seen_) != 122467:
        raise ValueError("Scaler was not fitted on the recorded training population")
    lr = pipeline.named_steps["classifier"]
    if lr.C != 1.0 or lr.max_iter != 2000 or lr.random_state != 42:
        raise ValueError("Logistic configuration mismatch")
    expected = {
        "n_estimators": 200,
        "learning_rate": 0.05,
        "num_leaves": 15,
        "max_depth": 5,
        "min_child_samples": 100,
        "reg_lambda": 1.0,
        "max_bin": 63,
        "random_state": 42,
        "n_jobs": 1,
        "deterministic": True,
        "force_col_wise": True,
    }
    if any(models["lightgbm"].get_params().get(k) != v for k, v in expected.items()):
        raise ValueError("LightGBM configuration mismatch")
    return models, hashes


def notebook_records(path):
    """Recover printed historical values; never infer notebook customer scores or refit."""
    if file_hash(path) != NOTEBOOK_SHA:
        raise ValueError("Historical notebook changed; review its provenance before export")
    notebook = json.loads(path.read_text())
    text = "\n".join(
        "".join(o.get("text", [])) or "".join(o.get("data", {}).get("text/plain", []))
        for c in notebook["cells"]
        for o in c.get("outputs", [])
    )
    summaries = {
        ("logistic", "validation"): {
            "average_precision": 0.2087,
            "roc_auc": 0.6054,
            "lift_10pct": 1.83,
            "brier_score": 0.1211,
        },
        ("lightgbm", "validation"): {
            "average_precision": 0.2209,
            "roc_auc": 0.6278,
            "lift_10pct": 1.93,
            "brier_score": 0.1194,
        },
        ("lightgbm", "test"): {
            "average_precision": 0.2134,
            "roc_auc": 0.6238,
            "lift_10pct": 2.08,
            "brier_score": 0.1130,
            "rows": 33020,
            "prevalence": 0.1345,
            "baseline_brier": 0.1164,
            "relative_brier_improvement": 0.0287,
        },
    }
    provenance = "historical_notebook_saved_output"
    for (model, split), metrics in summaries.items():
        for key, value in metrics.items():
            if key not in ("rows", "prevalence", "relative_brier_improvement"):
                token = f"{value:.2f}x" if key == "lift_10pct" else f"{value:.4f}"
                if token not in text:
                    raise ValueError(f"Historical notebook output not found: {token}")
            yield (
                "metrics",
                metric_record(
                    NOTEBOOK,
                    model,
                    "notebook-" + NOTEBOOK_SHA,
                    split,
                    key,
                    value,
                    provenance,
                    "reported_rounded",
                ),
            )
    permutation = [0.022795, 0.054013, 0.008695, 0.010550, 0.018373, 0.0, 0.006381]
    splits = [331, 327, 204, 161, 212, 0, 34]
    for feature, importance, count in zip(FEATURES, permutation, splits, strict=True):
        if f"{importance:.6f}" not in text:
            raise ValueError("Permutation output not found")
        for method, value in [
            ("permutation_validation_ap_drop", importance),
            ("split_count", count),
        ]:
            yield (
                "importance",
                {
                    "experiment_id": NOTEBOOK,
                    "model_name": "lightgbm",
                    "model_version": "notebook-" + NOTEBOOK_SHA,
                    "feature_name": feature,
                    "importance_method": method,
                    "importance_value": value,
                    "dataset_split": "validation" if method.startswith("permutation") else "train",
                    "provenance": provenance,
                },
            )


def saved_records(report, hashes):
    for split in ("validation", "test"):
        for model in MODELS:
            result = report["evaluations"][split][model]
            for metric, value in result["metrics"].items():
                yield (
                    "metrics",
                    metric_record(
                        SCRIPTED,
                        model,
                        hashes[model],
                        split,
                        metric,
                        value,
                        "original_scripted_metrics_json",
                        "stored_full_precision",
                    ),
                )
            bins = result["calibration"]
            if sum(b["rows"] for b in bins) != report["splits"][split]["customers"]:
                raise ValueError("Saved calibration counts do not reconcile")
            for b in bins:
                if b["rows"] and any(
                    b[k] is None or not 0 <= b[k] <= 1
                    for k in ("mean_probability", "observed_rate")
                ):
                    raise ValueError("Invalid saved calibration")
                yield (
                    "calibration",
                    {
                        "experiment_id": SCRIPTED,
                        "model_name": model,
                        "model_version": hashes[model],
                        "dataset_split": split,
                        "probability_bin_lower": b["lower"],
                        "probability_bin_upper": b["upper"],
                        "customer_count": b["rows"],
                        "mean_predicted_probability": b["mean_probability"],
                        "observed_positive_rate": b["observed_rate"],
                        "provenance": "original_scripted_metrics_json",
                    },
                )
    for row in report["importance"]:
        for model, method, key in [
            (
                "logistic",
                "standardized_log1p_coefficient",
                "logistic_standardized_log1p_coefficient",
            ),
            ("lightgbm", "gain", "lightgbm_gain"),
            ("lightgbm", "split_count", "lightgbm_splits"),
        ]:
            yield (
                "importance",
                {
                    "experiment_id": SCRIPTED,
                    "model_name": model,
                    "model_version": hashes[model],
                    "feature_name": row["feature"],
                    "importance_method": method,
                    "importance_value": row[key],
                    "dataset_split": "train",
                    "provenance": "original_scripted_metrics_json",
                },
            )


def validate_package(path):
    meta = json.loads((path / "package.json").read_text())
    counts, checksums = Counter(), [0, 0]
    digest = hashlib.sha256()
    seen = set()
    prediction_counts, positive_counts = Counter(), Counter()
    with gzip.open(path / "rows.jsonl.gz", "rt") as handle:
        for line in handle:
            record = json.loads(line)
            kind, payload = record["record_type"], record["payload"]
            if kind not in KINDS:
                raise ValueError("Unknown reporting record")
            row = json.loads(payload)
            if canonical(row) != payload:
                raise ValueError("Noncanonical reporting payload")
            required = (
                "experiment_id",
                "model_name",
                "model_version",
                "dataset_split",
                "provenance",
            )
            if any(not isinstance(row.get(k), str) or not row[k] for k in required):
                raise ValueError("Missing reporting identity/provenance")
            key = (kind, *(row[k] for k in required[:4]))
            if kind == "predictions":
                if row["experiment_id"] != SCRIPTED or row["provenance"] != "artifact_inference":
                    raise ValueError("Only scripted artifact inference may supply predictions")
                if (
                    row["dataset_split"] not in ("validation", "test")
                    or row["model_name"] not in MODELS
                ):
                    raise ValueError("Unexpected inference scope")
                if type(row["client_id"]) is not int or row["actual_target"] not in (0, 1):
                    raise ValueError("Invalid prediction identifier/target")
                probabilities_checked([row["prediction_probability"]], 1)
                timestamp = datetime.fromisoformat(row["first_purchase_ts"])
                if timestamp.tzinfo is None:
                    raise ValueError("Missing computational timestamp convention")
                key += (row["client_id"],)
                group = row["dataset_split"] + ":" + row["model_name"]
                prediction_counts[group] += 1
                positive_counts[group] += row["actual_target"]
            elif kind == "metrics":
                metric_record(
                    *(row[k] for k in required[:4]),
                    row["metric_name"],
                    row["metric_value"],
                    row["provenance"],
                    row["value_precision"],
                )
                key += (row["metric_name"],)
            elif kind == "importance":
                if row["feature_name"] not in FEATURES or not math.isfinite(
                    row["importance_value"]
                ):
                    raise ValueError("Invalid importance record")
                key += (row["feature_name"], row["importance_method"])
            else:
                if row["experiment_id"] != SCRIPTED:
                    raise ValueError("Notebook numerical calibration is unavailable")
                lower, upper = row["probability_bin_lower"], row["probability_bin_upper"]
                if not 0 <= lower < upper <= 1 or row["customer_count"] < 0:
                    raise ValueError("Invalid calibration bin")
                for field in ("mean_predicted_probability", "observed_positive_rate"):
                    value = row[field]
                    if (row["customer_count"] == 0 and value is not None) or (
                        row["customer_count"] > 0 and (value is None or not 0 <= value <= 1)
                    ):
                        raise ValueError("Invalid calibration summary")
                key += (lower, upper)
            if key in seen:
                raise ValueError("Duplicate reporting key")
            seen.add(key)
            counts[kind] += 1
            a, b = row_hashes(kind, payload)
            checksums[0] += a
            checksums[1] += b
            digest.update(line.encode())
    if dict(counts) != meta["counts"] or list(map(str, checksums)) != meta["checksums"]:
        raise ValueError("Prepared rows do not match package checksums")
    if digest.hexdigest() != meta["bundle_digest"]:
        raise ValueError("Prepared bundle digest mismatch")
    if "prediction_counts" in meta and dict(prediction_counts) != meta["prediction_counts"]:
        raise ValueError("Prediction population mismatch")
    if "prediction_positives" in meta and dict(positive_counts) != meta["prediction_positives"]:
        raise ValueError("Prediction target mismatch")
    return meta


def prepare(artifacts, notebook, output):
    artifacts, notebook, output = Path(artifacts), Path(notebook), Path(output)
    report = json.loads((artifacts / "metrics.json").read_text())
    selection = json.loads((artifacts / "selection.json").read_text())
    if file_hash(notebook) != NOTEBOOK_SHA:
        raise ValueError("Historical notebook checksum mismatch")
    models, hashes = compatible_models(artifacts, report, selection)
    frame, dataset_sha = load_dataset()
    if dataset_sha != report["dataset_sha256"]:
        raise ValueError("Feature dataset checksum differs from historical experiment")
    splits, excluded = chronological_split(frame)
    for split, subset in splits.items():
        if (
            len(subset) != report["splits"][split]["customers"]
            or int(subset.target_30d.sum()) != report["splits"][split]["positives"]
        ):
            raise ValueError("Split population/targets mismatch")
    identity = {
        "policy": POLICY,
        "dataset_sha256": dataset_sha,
        "artifact_hashes": hashes,
        "metrics_sha256": file_hash(artifacts / "metrics.json"),
        "selection_sha256": file_hash(artifacts / "selection.json"),
        "notebook_sha256": file_hash(notebook),
    }
    export_id = hashlib.sha256(canonical(identity).encode()).hexdigest()
    if output.exists():
        meta = validate_package(output)
        if meta["identity"] != identity:
            raise ValueError("Existing output belongs to another experiment/package")
        return meta
    output.mkdir(parents=True)
    counts, checksums, digest = Counter(), [0, 0], hashlib.sha256()
    scored_at = datetime.now(UTC).isoformat()
    try:
        with gzip.open(output / "rows.jsonl.gz", "wt") as handle:

            def emit(kind, row):
                payload = canonical(row)
                line = canonical({"record_type": kind, "payload": payload}) + "\n"
                handle.write(line)
                digest.update(line.encode())
                counts[kind] += 1
                a, b = row_hashes(kind, payload)
                checksums[0] += a
                checksums[1] += b

            for split in ("validation", "test"):
                subset = splits[split]
                for model_name, model in models.items():
                    probabilities = probabilities_checked(
                        model.predict_proba(subset[FEATURES])[:, 1], len(subset)
                    )
                    saved_bins = report["evaluations"][split][model_name]["calibration"]
                    # Consistency check against frozen summaries, not a new evaluation report.
                    if not np.isclose(
                        probabilities.mean(),
                        report["evaluations"][split][model_name]["metrics"]["mean_probability"],
                        rtol=1e-12,
                        atol=1e-14,
                    ):
                        raise ValueError("Inference disagrees with saved mean probability")
                    for b in saved_bins:
                        mask = (probabilities >= b["lower"]) & (probabilities < b["upper"])
                        if b["upper"] == 1:
                            mask |= probabilities == 1
                        if int(mask.sum()) != b["rows"]:
                            raise ValueError("Inference disagrees with saved calibration counts")
                        if mask.any() and (
                            not np.isclose(
                                probabilities[mask].mean(),
                                b["mean_probability"],
                                rtol=1e-12,
                                atol=1e-14,
                            )
                            or not np.isclose(
                                subset.target_30d.to_numpy()[mask].mean(),
                                b["observed_rate"],
                                rtol=1e-12,
                                atol=1e-14,
                            )
                        ):
                            raise ValueError("Inference disagrees with saved calibration summaries")
                    for client_id, timestamp, target, probability in zip(
                        subset.client_id,
                        subset.first_purchase_ts,
                        subset.target_30d,
                        probabilities,
                        strict=True,
                    ):
                        emit(
                            "predictions",
                            {
                                "experiment_id": SCRIPTED,
                                "model_name": model_name,
                                "model_version": hashes[model_name],
                                "client_id": int(client_id),
                                "first_purchase_ts": timestamp.isoformat(),
                                "dataset_split": split,
                                "prediction_probability": float(probability),
                                "actual_target": int(target),
                                "provenance": "artifact_inference",
                            },
                        )
            for kind, row in saved_records(report, hashes):
                emit(kind, row)
            for kind, row in notebook_records(notebook):
                emit(kind, row)
        if counts["predictions"] != 335160:
            raise ValueError("Unexpected prediction count")
        meta = {
            "export_id": export_id,
            "identity": identity,
            "counts": dict(counts),
            "checksums": list(map(str, checksums)),
            "bundle_digest": digest.hexdigest(),
            "scored_at": scored_at,
            "runtime_versions": {p: importlib.metadata.version(p) for p in report["versions"]},
            "runtime_python": platform.python_version(),
            "historical_python": report["python"],
            "experiments": {
                SCRIPTED: {
                    "source": "metrics.json + selection.json + trusted joblib artifacts",
                    "features": report["features"],
                    "versions": report["versions"],
                    "selection": selection,
                    "split_boundaries": report["split_boundaries"],
                    "training_date": report["training_date"],
                    "selection_date": report["selection_date"],
                    "evaluation_as_of": report["evaluation_as_of"],
                    "scoring_provenance": "artifact_inference",
                },
                NOTEBOOK: {
                    "source": "hash-pinned saved notebook outputs; reported rounded values",
                    "predictions_available": False,
                    "numerical_calibration_available": False,
                    "historical_runtime_versions": "not fully recorded",
                    "logistic": "StandardScaler raw counts; max_iter=1000, random_state=42",
                    "lightgbm": (
                        "n_estimators=100, learning_rate=0.05, "
                        "max_depth=4, random_state=42, verbosity=-1"
                    ),
                },
            },
            "validation_customers": len(splits["validation"]),
            "test_customers": len(splits["test"]),
            "excluded_customers": excluded,
            "prediction_counts": {
                s + ":" + m: len(splits[s]) for s in ("validation", "test") for m in MODELS
            },
            "prediction_positives": {
                s + ":" + m: int(splits[s].target_30d.sum())
                for s in ("validation", "test")
                for m in MODELS
            },
            "compatibility": (
                "Exact recorded package versions, feature order, model configuration "
                "and dataset checksum matched"
            ),
            "predictions": (
                "Regenerated inference only; no historical performance metrics recalculated"
            ),
        }
        (output / "package.json").write_text(json.dumps(meta, indent=2))
        return validate_package(output)
    except Exception:
        # Keep incomplete local evidence; no package manifest means it cannot publish.
        raise
