"""Frozen V4.1 experiment with calendar-date label maturity and a final-only holdout."""

import hashlib
import importlib.metadata
import io
import json
import platform
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from threadpoolctl import threadpool_limits

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment
from ecommerce_analytics.models.baseline import evaluate

FEATURES = [
    "page_views_30d",
    "unique_pages_30d",
    "cart_adds_30d",
    "cart_removals_30d",
    "searches_30d",
    "has_cart_activity_30d",
    "has_behavioral_activity_30d",
]
COUNTS = FEATURES[:5]
SPLITS = {
    "train": ("2022-07-23 00:12:25", "2022-08-16"),
    "validation": ("2022-09-15", "2022-10-01"),
    "test": ("2022-11-01", "2022-11-08"),
}
TRAINING_DATE = pd.Timestamp("2022-09-15", tz="UTC")
SELECTION_DATE = pd.Timestamp("2022-10-31", tz="UTC")
OBSERVATION_END = pd.Timestamp("2022-12-08", tz="UTC")
TABLE = "synerise_analytics.ml_customer_features"
SEED = 42


def validate_dataset(frame: pd.DataFrame, historical: bool = True) -> None:
    """Validate the compact feature dataset without silently imputing bad inputs."""
    required = {"client_id", "first_purchase_ts", "first_purchase_month", "target_30d", *FEATURES}
    if set(frame.columns) != required or frame.empty or frame.isna().any().any():
        raise ValueError("Unexpected columns, empty data or missing values.")
    if frame.client_id.duplicated().any():
        raise ValueError("Duplicate customers.")
    values = frame[FEATURES].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
        raise ValueError("Features must be finite nonnegative integer counts/flags.")
    for column in ["target_30d", *FEATURES[5:]]:
        if not frame[column].isin([0, 1]).all():
            raise ValueError("Target/activity indicators must be binary.")
    if (frame.unique_pages_30d > frame.page_views_30d).any():
        raise ValueError("Distinct pages exceed views.")
    if not (frame.has_cart_activity_30d == (frame.cart_adds_30d > 0)).all():
        raise ValueError("Cart flag must reflect additions only.")
    active = frame[["page_views_30d", "cart_adds_30d", "cart_removals_30d", "searches_30d"]]
    if not (frame.has_behavioral_activity_30d == active.gt(0).any(axis=1)).all():
        raise ValueError("Behavior flag disagrees with counts.")
    timestamps = frame.first_purchase_ts
    if str(timestamps.dt.tz) != "UTC":
        raise ValueError("Explicit UTC computational parsing required.")
    if (
        not timestamps.dt.strftime("%Y-%m-01")
        .eq(pd.to_datetime(frame.first_purchase_month).dt.strftime("%Y-%m-%d"))
        .all()
    ):
        raise ValueError("Cohort month mismatch.")
    if historical and (len(frame) != 547914 or int(frame.target_30d.sum()) != 74781):
        raise ValueError("Historical population/target counts changed.")
    if not timestamps.between(
        pd.Timestamp(SPLITS["train"][0], tz="UTC"),
        pd.Timestamp("2022-11-08", tz="UTC"),
        inclusive="left",
    ).all():
        raise ValueError("Rows outside established eligibility.")


def load_dataset() -> tuple[pd.DataFrame, str]:
    """Only SELECT explicit columns from the existing small analytical feature table."""
    columns = ["client_id", "first_purchase_ts", "first_purchase_month", "target_30d", *FEATURES]
    client = configured_client(environment(), "ADMIN")
    raw = client._request(
        f"SELECT {', '.join(columns)} FROM {TABLE} ORDER BY client_id FORMAT TabSeparatedWithNames"
    )
    frame = pd.read_csv(io.BytesIO(raw), sep="\t", na_values=[r"\N"])
    frame["first_purchase_ts"] = pd.to_datetime(frame.first_purchase_ts, utc=True, errors="raise")
    validate_dataset(frame)
    return frame, hashlib.sha256(raw).hexdigest()


def label_available_at(timestamps: pd.Series) -> pd.Series:
    """Day +30 is inclusive: a negative is knowable at midnight of day +31."""
    return timestamps.dt.normalize() + pd.Timedelta(days=31)


def require_maturity(frame: pd.DataFrame, as_of: pd.Timestamp) -> None:
    if (label_available_at(frame.first_purchase_ts) > as_of).any():
        raise ValueError(f"Unavailable calendar-date outcomes at {as_of.isoformat()}")


def chronological_split(frame: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], int]:
    splits = {}
    for name, (start, end) in SPLITS.items():
        mask = frame.first_purchase_ts.ge(pd.Timestamp(start, tz="UTC")) & (
            frame.first_purchase_ts.lt(pd.Timestamp(end, tz="UTC"))
        )
        splits[name] = frame.loc[mask].copy()
        if splits[name].empty or splits[name].target_30d.nunique() != 2:
            raise ValueError(f"Empty/single-class {name} split.")
    require_maturity(splits["train"], TRAINING_DATE)
    require_maturity(splits["validation"], SELECTION_DATE)
    require_maturity(splits["test"], OBSERVATION_END)
    if TRAINING_DATE > splits["validation"].first_purchase_ts.min():
        raise ValueError("Training follows validation prediction time.")
    if SELECTION_DATE > splits["test"].first_purchase_ts.min():
        raise ValueError("Model selection follows test prediction time.")
    return splits, len(frame) - sum(len(x) for x in splits.values())


def fit_models(train: pd.DataFrame) -> dict:
    """Fixed initial hyperparameters; never pass validation/test to fit or early stopping."""
    models = {
        "dummy": DummyClassifier(strategy="prior", random_state=SEED),
        "logistic": Pipeline(
            [
                ("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                ("scale", StandardScaler()),
                ("classifier", LogisticRegression(C=1.0, max_iter=2000, random_state=SEED)),
            ]
        ),
        "lightgbm": LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=15,
            max_depth=5,
            min_child_samples=100,
            reg_lambda=1.0,
            max_bin=63,
            random_state=SEED,
            n_jobs=1,
            deterministic=True,
            force_col_wise=True,
            verbosity=-1,
        ),
    }
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        for model in models.values():
            model.fit(train[FEATURES], train.target_30d)
    return models


def select_threshold(y: np.ndarray, probabilities: np.ndarray) -> float:
    """Maximum validation F1; ties choose the higher threshold. Never use holdout labels."""
    precision, recall, thresholds = precision_recall_curve(y, probabilities)
    f1 = np.divide(
        2 * precision[:-1] * recall[:-1],
        precision[:-1] + recall[:-1],
        out=np.zeros_like(precision[:-1]),
        where=(precision[:-1] + recall[:-1]) > 0,
    )
    best = np.flatnonzero(f1 == f1.max())[-1]
    return float(thresholds[best])


def score(frame: pd.DataFrame, probabilities: np.ndarray, threshold: float) -> dict:
    """Reuse validated tie-aware ranking and calibration diagnostics from Phase 2.4."""
    y = frame.target_30d.to_numpy()
    tables = evaluate(y, probabilities, frame.client_id.to_numpy())
    metrics = tables["metrics"].iloc[0].to_dict()
    ranking = tables["ranking"].loc[tables["ranking"].fraction == 0.10].iloc[0]
    predictions = probabilities >= threshold
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    metrics.update(
        {
            "threshold": threshold,
            "precision": float(tp / (tp + fp)) if tp + fp else 0.0,
            "recall": float(tp / (tp + fn)),
            "f1": float(f1_score(y, predictions)),
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
            "lift_10pct": float(ranking.tie_expected_lift_at_k),
            "precision_10pct": float(ranking.tie_expected_precision_at_k),
            "top_k": int(ranking.k),
            "boundary_tie_customers": int(ranking.cutoff_tie_customers),
        }
    )
    calibration = (
        tables["calibration"]
        .astype(object)
        .where(tables["calibration"].notna(), None)
        .to_dict("records")
    )
    return {"metrics": metrics, "calibration": calibration}


def activity_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "cart_additions": frame.has_cart_activity_30d.eq(1),
        "other_behavior": frame.has_cart_activity_30d.eq(0)
        & frame.has_behavioral_activity_30d.eq(1),
        "no_behavior": frame.has_behavioral_activity_30d.eq(0),
    }


def run_experiment(output: Path) -> dict:
    if output.exists():
        raise ValueError(
            "Use a fresh output directory; prior holdout results must not be overwritten."
        )
    started = time.perf_counter()
    frame, digest = load_dataset()
    splits, excluded = chronological_split(frame)
    output.mkdir(parents=True)
    models = fit_models(splits["train"])
    validation = splits["validation"]
    thresholds, evaluations = {}, {"validation": {}, "test": {}}
    for name, model in models.items():
        probabilities = model.predict_proba(validation[FEATURES])[:, 1]
        thresholds[name] = select_threshold(validation.target_30d.to_numpy(), probabilities)
        evaluations["validation"][name] = score(validation, probabilities, thresholds[name])
    winner = max(models, key=lambda n: evaluations["validation"][n]["metrics"]["average_precision"])
    # Persist the development decision BEFORE the first test prediction/evaluation.
    decision = {
        "selected_model": winner,
        "thresholds": thresholds,
        "primary_metric": "average_precision",
    }
    (output / "selection.json").write_text(json.dumps(decision, indent=2))
    for name, model in models.items():
        joblib.dump(model, output / f"{name}.joblib")
    groups = {}
    for split in ("validation", "test"):
        subset = splits[split]
        groups[split] = {}
        for name, model in models.items():
            probabilities = model.predict_proba(subset[FEATURES])[:, 1]
            if split == "test":
                evaluations[split][name] = score(subset, probabilities, thresholds[name])
            groups[split][name] = {}
            for group, mask in activity_masks(subset).items():
                part = subset.loc[mask]
                if part.target_30d.nunique() != 2:
                    raise ValueError(
                        "Activity group needs both classes for the requested diagnostics."
                    )
                groups[split][name][group] = score(part, probabilities[mask], thresholds[name])
    importance = pd.DataFrame(
        {
            "feature": FEATURES,
            "logistic_standardized_log1p_coefficient": models["logistic"]
            .named_steps["classifier"]
            .coef_[0],
            "lightgbm_gain": models["lightgbm"].booster_.feature_importance(importance_type="gain"),
            "lightgbm_splits": models["lightgbm"].booster_.feature_importance(
                importance_type="split"
            ),
        }
    )
    report = {
        "table": TABLE,
        "dataset_sha256": digest,
        "seed": SEED,
        "features": FEATURES,
        "training_date": str(TRAINING_DATE),
        "selection_date": str(SELECTION_DATE),
        "evaluation_as_of": str(OBSERVATION_END),
        "split_boundaries": SPLITS,
        "excluded_customers": excluded,
        "population": len(frame),
        "positives": int(frame.target_30d.sum()),
        "splits": {
            name: {
                "customers": len(x),
                "positives": int(x.target_30d.sum()),
                "negatives": int(len(x) - x.target_30d.sum()),
                "prevalence": float(x.target_30d.mean()),
                "last_label_available": str(label_available_at(x.first_purchase_ts).max()),
            }
            for name, x in splits.items()
        },
        "selection": decision,
        "evaluations": evaluations,
        "activity_groups": groups,
        "importance": importance.to_dict("records"),
        "logistic_intercept": float(models["logistic"].named_steps["classifier"].intercept_[0]),
        "versions": {
            p: importlib.metadata.version(p)
            for p in (
                "numpy",
                "pandas",
                "scikit-learn",
                "lightgbm",
                "scipy",
                "joblib",
                "threadpoolctl",
            )
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "elapsed_seconds": time.perf_counter() - started,
    }
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    return report
