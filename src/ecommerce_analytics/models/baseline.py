"""Chronological, fixed-specification baselines over the validated snapshot table."""

import platform
import warnings
from itertools import combinations
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from ecommerce_analytics.analytics.exploration import ExplorationError
from ecommerce_analytics.features.customer_snapshots import FEATURES

SPLITS = {
    "train": ("2019-11-01", "2019-12-01"),
    "validation": ("2020-01-01",),
    "test": ("2020-02-01",),
}
THRESHOLDS = (0.05, 0.10, 0.20, 0.50)
TOP_FRACTIONS = (0.01, 0.05, 0.10)


def inspect_dataset(database: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Load only the compact customer snapshots, never raw event history."""
    if not database.is_file():
        raise ExplorationError(f"Existing database not found: {database}")
    with duckdb.connect(str(database), read_only=True) as con:
        schema = con.sql("DESCRIBE customer_snapshot_features").df()
        frame = con.sql(
            "SELECT * FROM customer_snapshot_features ORDER BY prediction_date, user_id"
        ).df()
    required = {"prediction_date", "user_id", "target_14d", *FEATURES}
    if set(frame.columns) != required:
        raise ExplorationError("Unexpected feature schema; review the explicit feature allowlist.")
    if frame[["prediction_date", "user_id", "target_14d"]].isna().any().any():
        raise ExplorationError("Missing snapshot keys or target.")
    if frame.duplicated(["prediction_date", "user_id"]).any():
        raise ExplorationError("Duplicate customer snapshot keys.")
    if not frame.target_14d.isin([0, 1]).all():
        raise ExplorationError("Target must be binary.")
    quality, distributions = [], []
    for name in FEATURES:
        x = frame[name].to_numpy(dtype=float)
        quality.append((name, int(np.isnan(x).sum()), int(np.isinf(x).sum()), int((x < 0).sum())))
        if not np.isfinite(x).all() or (x < 0).any():
            continue  # Aggregate quality validation below rejects invalid columns.
        for day, group in frame.groupby("prediction_date"):
            values = group[name]
            distributions.append(
                (
                    day,
                    name,
                    values.min(),
                    values.quantile(0.25),
                    values.median(),
                    values.quantile(0.75),
                    values.quantile(0.95),
                    values.max(),
                    values.mean(),
                    float((values == 0).mean()),
                )
            )
    quality_frame = pd.DataFrame(quality, columns=["feature", "missing", "infinite", "negative"])
    if quality_frame[["missing", "infinite", "negative"]].to_numpy().any():
        raise ExplorationError(f"Invalid feature values:\n{quality_frame.to_string(index=False)}")
    dates = sorted(frame.prediction_date.unique())
    overlap = []
    for a, b in combinations(dates, 2):
        left = set(frame.loc[frame.prediction_date == a, "user_id"])
        right = set(frame.loc[frame.prediction_date == b, "user_id"])
        overlap.append(
            (a, b, len(left & right), len(left), len(right), len(left & right) / len(right))
        )
    balance = (
        frame.groupby("prediction_date")
        .target_14d.agg(rows="size", positives="sum", positive_rate="mean")
        .reset_index()
    )
    return frame, {
        "feature_schema": schema,
        "feature_quality": quality_frame,
        "feature_distributions": pd.DataFrame(
            distributions,
            columns=[
                "prediction_date",
                "feature",
                "min",
                "p25",
                "median",
                "p75",
                "p95",
                "max",
                "mean",
                "zero_fraction",
            ],
        ),
        "class_balance": balance,
        "customer_overlap": pd.DataFrame(
            overlap,
            columns=[
                "earlier_snapshot",
                "later_snapshot",
                "shared_customers",
                "earlier_customers",
                "later_customers",
                "later_overlap_fraction",
            ],
        ),
    }


def chronological_split(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    expected = {pd.Timestamp(d) for dates in SPLITS.values() for d in dates}
    if set(frame.prediction_date.unique()) != expected:
        raise ExplorationError("Exactly the four documented snapshot dates are required.")
    splits = {
        name: frame[frame.prediction_date.isin(pd.to_datetime(dates))].copy()
        for name, dates in SPLITS.items()
    }
    for name, subset in splits.items():
        if subset.empty or subset.target_14d.nunique() != 2:
            raise ExplorationError(f"{name} requires both classes.")
    for earlier, later in (("train", "validation"), ("validation", "test")):
        label_end = splits[earlier].prediction_date.max() + pd.Timedelta(days=14)
        if label_end >= splits[later].prediction_date.min():
            raise ExplorationError(
                "Earlier label windows must end before the next evaluation date."
            )
    return splits


def fit_models(train: pd.DataFrame) -> dict[str, Pipeline]:
    """All transforms and estimators fit on training rows only; no tuning."""
    x, y = train[list(FEATURES)], train.target_14d
    models = {
        "constant": Pipeline([("model", DummyClassifier(strategy="prior"))]),
        "logistic": Pipeline(
            [
                ("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(C=1.0, solver="lbfgs", max_iter=2000, random_state=42),
                ),
            ]
        ),
    }
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        for model in models.values():
            model.fit(x, y)
    return models


def evaluate(y: np.ndarray, probabilities: np.ndarray, ids: np.ndarray) -> dict[str, pd.DataFrame]:
    """Fixed thresholds, fixed budgets, and tie-aware expected ranking metrics."""
    y, probabilities = np.asarray(y), np.asarray(probabilities, dtype=float)
    if len(y) != len(probabilities) or not len(y) or set(np.unique(y)) != {0, 1}:
        raise ValueError("Evaluation requires aligned probabilities and both classes.")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Invalid predicted probabilities.")
    metrics = pd.DataFrame(
        [
            {
                "rows": len(y),
                "positives": int(y.sum()),
                "prevalence": y.mean(),
                "roc_auc": roc_auc_score(y, probabilities),
                "average_precision": average_precision_score(y, probabilities),
                "brier_score": brier_score_loss(y, probabilities),
                "log_loss": log_loss(y, probabilities, labels=[0, 1]),
                "mean_probability": probabilities.mean(),
            }
        ]
    )
    thresholds = []
    for threshold in THRESHOLDS:
        pred = probabilities >= threshold
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        thresholds.append(
            (
                threshold,
                precision_score(y, pred, zero_division=0),
                recall_score(y, pred, zero_division=0),
                int(pred.sum()),
                tn,
                fp,
                fn,
                tp,
            )
        )
    ranking = []
    # IDs only provide a deterministic, nonpredictive tie-break for operational top K.
    order = np.lexsort((np.asarray(ids, dtype=str), -probabilities))
    for fraction in TOP_FRACTIONS:
        k = max(1, int(np.ceil(len(y) * fraction)))
        cutoff = probabilities[order[k - 1]]
        above, tied = probabilities > cutoff, probabilities == cutoff
        slots = k - int(above.sum())
        expected_hits = y[above].sum() + slots * y[tied].mean()
        precision = float(y[order[:k]].mean())
        ranking.append(
            (
                fraction,
                k,
                precision,
                precision / y.mean(),
                y[order[:k]].sum() / y.sum(),
                expected_hits / k,
                (expected_hits / k) / y.mean(),
                int(tied.sum()),
            )
        )
    bins = np.minimum((probabilities * 10).astype(int), 9)
    calibration = []
    for index in range(10):
        mask = bins == index
        count = int(mask.sum())
        calibration.append(
            (
                index / 10,
                (index + 1) / 10,
                count,
                probabilities[mask].mean() if count else np.nan,
                y[mask].mean() if count else np.nan,
            )
        )
    calibration_frame = pd.DataFrame(
        calibration, columns=["lower", "upper", "rows", "mean_probability", "observed_rate"]
    )
    metrics["ece_10_bins"] = sum(
        row.rows / len(y) * abs(row.mean_probability - row.observed_rate)
        for row in calibration_frame.itertuples()
        if row.rows
    )
    return {
        "metrics": metrics,
        "thresholds": pd.DataFrame(
            thresholds,
            columns=[
                "threshold",
                "precision",
                "recall",
                "predicted_positive",
                "tn",
                "fp",
                "fn",
                "tp",
            ],
        ),
        "ranking": pd.DataFrame(
            ranking,
            columns=[
                "fraction",
                "k",
                "precision_at_k",
                "lift_at_k",
                "recall_at_k",
                "tie_expected_precision_at_k",
                "tie_expected_lift_at_k",
                "cutoff_tie_customers",
            ],
        ),
        "calibration": calibration_frame,
    }


def run_baselines(database: Path) -> dict[str, pd.DataFrame]:
    frame, tables = inspect_dataset(database)
    splits = chronological_split(frame)
    models = fit_models(splits["train"])
    outputs: dict[str, list[pd.DataFrame]] = {}
    for split in ("validation", "test"):
        subset = splits[split]
        for name, model in models.items():
            result = evaluate(
                subset.target_14d.to_numpy(),
                model.predict_proba(subset[list(FEATURES)])[:, 1],
                subset.user_id.to_numpy(),
            )
            for kind, values in result.items():
                values.insert(0, "split", split)
                values.insert(1, "model", name)
                outputs.setdefault(kind, []).append(values)
    tables.update({kind: pd.concat(values, ignore_index=True) for kind, values in outputs.items()})
    tables["split_summary"] = pd.DataFrame(
        [
            (
                name,
                len(subset),
                subset.user_id.nunique(),
                subset.target_14d.mean(),
                subset.prediction_date.min(),
                subset.prediction_date.max(),
                subset.prediction_date.max() + pd.Timedelta(days=14),
            )
            for name, subset in splits.items()
        ],
        columns=[
            "split",
            "rows",
            "customers",
            "prevalence",
            "first_snapshot",
            "last_snapshot",
            "last_label_end_exclusive",
        ],
    )
    tables["coefficients"] = pd.DataFrame(
        {
            "feature": list(FEATURES),
            "standardized_log_coefficient": models["logistic"].named_steps["model"].coef_[0],
        }
    )
    tables["versions"] = pd.DataFrame(
        [
            {
                "python": platform.python_version(),
                "sklearn": sklearn.__version__,
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "duckdb": duckdb.__version__,
                "training_prevalence": splits["train"].target_14d.mean(),
                "logistic_intercept": models["logistic"].named_steps["model"].intercept_[0],
                "iterations": int(models["logistic"].named_steps["model"].n_iter_[0]),
            }
        ]
    )
    return tables
