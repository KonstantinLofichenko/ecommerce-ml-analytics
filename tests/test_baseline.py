"""Known metric outcomes and training/evaluation separation."""

import numpy as np
import pandas as pd
import pytest

from ecommerce_analytics.analytics.exploration import ExplorationError
from ecommerce_analytics.features.customer_snapshots import FEATURES
from ecommerce_analytics.models.baseline import chronological_split, evaluate, fit_models


def fixture() -> pd.DataFrame:
    rows = []
    for day in ("2019-11-01", "2019-12-01", "2020-01-01", "2020-02-01"):
        for i in range(20):
            rows.append(
                {
                    "prediction_date": pd.Timestamp(day),
                    "user_id": str(i),
                    "target_14d": i % 2,
                    **{f: i for f in FEATURES},
                }
            )
    return pd.DataFrame(rows)


def test_chronological_split_and_window_separation() -> None:
    frame = fixture()
    splits = chronological_split(frame)
    assert [len(splits[k]) for k in ("train", "validation", "test")] == [40, 20, 20]
    assert splits["train"].prediction_date.max() + pd.Timedelta(days=14) < (
        splits["validation"].prediction_date.min()
    )
    assert set(splits["test"].user_id) == set(splits["train"].user_id)
    with pytest.raises(ExplorationError):
        chronological_split(frame[frame.prediction_date != pd.Timestamp("2020-02-01")])


def test_training_only_preprocessing_and_feature_allowlist() -> None:
    splits = chronological_split(fixture())
    model = fit_models(splits["train"])["logistic"]
    scaler = model.named_steps["scale"]
    np.testing.assert_allclose(scaler.mean_, np.log1p(splits["train"][list(FEATURES)]).mean())
    assert list(model.feature_names_in_) == list(FEATURES)
    before = scaler.mean_.copy()
    future = splits["test"][list(FEATURES)] * 100000
    model.predict_proba(future)
    np.testing.assert_array_equal(scaler.mean_, before)


def test_perfect_ranking_thresholds_and_calibration() -> None:
    result = evaluate(np.array([0, 0, 1, 1]), np.array([0, 0.1, 0.8, 1]), np.array(list("abcd")))
    assert result["metrics"].iloc[0].roc_auc == 1
    assert result["metrics"].iloc[0].average_precision == 1
    row = result["thresholds"].query("threshold == .5").iloc[0]
    assert (row.tn, row.fp, row.fn, row.tp) == (2, 0, 0, 2)
    assert row.precision == row.recall == 1
    assert result["ranking"].iloc[0].precision_at_k == 1
    assert result["ranking"].iloc[0].lift_at_k == 2
    assert result["calibration"].rows.sum() == 4
    assert result["calibration"].iloc[-1].rows == 1  # Probability one included.


def test_constant_ties_and_training_prevalence() -> None:
    train = fixture().iloc[:20].copy()
    train["target_14d"] = [1] * 4 + [0] * 16
    model = fit_models(train)["constant"]
    np.testing.assert_allclose(model.predict_proba(train[list(FEATURES)])[:, 1], 0.2)
    result = evaluate(np.array([0, 1, 0, 1]), np.full(4, 0.2), np.array(list("abcd")))
    assert result["metrics"].iloc[0].roc_auc == 0.5
    assert result["metrics"].iloc[0].average_precision == 0.5
    np.testing.assert_allclose(result["ranking"].tie_expected_precision_at_k, 0.5)
    np.testing.assert_allclose(result["ranking"].tie_expected_lift_at_k, 1)
    row = result["thresholds"].query("threshold == .5").iloc[0]
    assert row.predicted_positive == 0
    assert row.precision == 0


def test_invalid_probability() -> None:
    with pytest.raises(ValueError):
        evaluate(np.array([0, 1]), np.array([0, np.inf]), np.array(["a", "b"]))


def test_inspection_and_end_to_end_pipeline(tmp_path) -> None:
    import duckdb

    from ecommerce_analytics.models.baseline import inspect_dataset, run_baselines
    from ecommerce_analytics.models.report import save_report

    path = tmp_path / "reference.duckdb"
    frame = fixture()
    with duckdb.connect(str(path)) as con:
        con.register("synthetic", frame)
        con.execute("CREATE TABLE customer_snapshot_features AS SELECT * FROM synthetic")
    tables = run_baselines(path)
    assert len(tables["metrics"]) == 4
    assert tables["feature_quality"][["missing", "infinite", "negative"]].to_numpy().sum() == 0
    assert (tables["customer_overlap"].shared_customers == 20).all()
    save_report(tables, tmp_path / "report.md", tmp_path / "outputs")
    assert "provisional baseline" in (tmp_path / "report.md").read_text()
    with duckdb.connect(str(path)) as con:
        assert con.sql("SELECT count(*) FROM customer_snapshot_features").fetchone()[0] == 80
        con.execute(
            "ALTER TABLE customer_snapshot_features ALTER days_since_last_event TYPE DOUBLE"
        )
        con.execute("UPDATE customer_snapshot_features SET days_since_last_event = 'Infinity'")
    with pytest.raises(ExplorationError, match="Invalid feature"):
        inspect_dataset(path)
