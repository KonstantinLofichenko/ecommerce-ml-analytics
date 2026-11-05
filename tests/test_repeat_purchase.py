"""Boundary, leakage-control and metric tests for the frozen V4.1 experiment."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from ecommerce_analytics.models.repeat_purchase import (  # noqa: E402
    FEATURES,
    SELECTION_DATE,
    TRAINING_DATE,
    chronological_split,
    fit_models,
    label_available_at,
    require_maturity,
    run_experiment,
    score,
    select_threshold,
    validate_dataset,
)


def frame_at(dates):
    frame = pd.DataFrame({"first_purchase_ts": pd.to_datetime(dates, utc=True, format="mixed")})
    frame["client_id"] = np.arange(len(frame))
    frame["first_purchase_month"] = frame.first_purchase_ts.dt.strftime("%Y-%m-01")
    frame["target_30d"] = np.arange(len(frame)) % 2
    for column in FEATURES:
        frame[column] = 0
    return frame


def test_calendar_target_matures_after_full_thirtieth_date():
    frame = frame_at(["2022-08-15 23:59:59"])
    assert label_available_at(frame.first_purchase_ts).iloc[0] == TRAINING_DATE
    require_maturity(frame, TRAINING_DATE)
    with pytest.raises(ValueError, match="Unavailable"):
        require_maturity(frame, TRAINING_DATE - pd.Timedelta(seconds=1))
    # Exact 720 hours expires earlier than the calendar-date target for a morning purchase.
    morning = frame_at(["2022-08-15 01:00:00"])
    with pytest.raises(ValueError, match="Unavailable"):
        require_maturity(morning, pd.Timestamp("2022-09-14 01:00:00", tz="UTC"))


def test_split_boundaries_and_gap_exclusion():
    frame = frame_at(
        [
            "2022-07-23 00:12:25",
            "2022-08-15 23:59:59",
            "2022-09-15",
            "2022-09-30 23:59:59",
            "2022-11-01",
            "2022-11-07 23:59:59",
            "2022-08-16",
            "2022-10-31",
        ]
    )
    splits, excluded = chronological_split(frame)
    assert [len(x) for x in splits.values()] == [2, 2, 2]
    assert excluded == 2
    assert label_available_at(splits["validation"].first_purchase_ts).max() == SELECTION_DATE


@pytest.mark.parametrize(
    "change", ["duplicate", "null", "infinite", "negative", "flag", "fraction"]
)
def test_bad_features_rejected(change):
    frame = frame_at(["2022-08-01", "2022-08-02"])
    if change == "duplicate":
        frame["client_id"] = 1
    elif change == "null":
        frame.loc[0, "target_30d"] = np.nan
    elif change in ("infinite", "fraction"):
        frame["page_views_30d"] = float("inf") if change == "infinite" else 0.5
    elif change == "negative":
        frame["searches_30d"] = -1
    else:
        frame["has_cart_activity_30d"] = 1
    with pytest.raises(ValueError):
        validate_dataset(frame, historical=False)


def test_predictor_allowlist_and_training_only_preprocessing():
    train = frame_at(["2022-08-01", "2022-08-02", "2022-08-03", "2022-08-04"])
    train["page_views_30d"] = [0, 2, 4, 6]
    train["has_behavioral_activity_30d"] = [0, 1, 1, 1]
    models = fit_models(train)
    scale = models["logistic"].named_steps["scale"]
    np.testing.assert_allclose(scale.mean_, np.log1p(train[FEATURES]).mean(axis=0))
    original_mean = scale.mean_.copy()
    holdout = train.copy()
    holdout["page_views_30d"] = 1_000_000
    models["logistic"].predict_proba(holdout[FEATURES])
    np.testing.assert_array_equal(scale.mean_, original_mean)
    assert models["logistic"].n_features_in_ == 7
    assert not {"client_id", "target_30d", "first_purchase_ts"}.intersection(FEATURES)
    assert models["dummy"].predict_proba(holdout[FEATURES])[0, 1] == 0.5


def test_threshold_selected_from_validation_and_tied_lift_is_one():
    assert select_threshold(np.array([0, 1, 0, 1]), np.array([0.1, 0.9, 0.2, 0.8])) == 0.8
    frame = frame_at(["2022-09-15"] * 20)
    result = score(frame, np.full(20, 0.5), 0.5)
    assert result["metrics"]["lift_10pct"] == 1
    assert result["metrics"]["average_precision"] == 0.5
    assert result["metrics"]["brier_score"] == 0.25
    assert result["metrics"]["tp"] == result["metrics"]["fp"] == 10
    assert sum(x["rows"] for x in result["calibration"]) == 20


def test_existing_artifacts_never_overwritten(tmp_path):
    with pytest.raises(ValueError, match="fresh output"):
        run_experiment(tmp_path)


def test_holdout_predictions_follow_persisted_selection(monkeypatch, tmp_path):
    from ecommerce_analytics.models import repeat_purchase as experiment

    frames = []
    for date, marker in [("2022-08-01", 10), ("2022-09-15", 20), ("2022-11-01", 30)]:
        part = frame_at([date] * 6)
        part["client_id"] += len(frames) * 6
        part["page_views_30d"] = [marker, marker, 1, 1, 0, 0]
        part["cart_adds_30d"] = [1, 1, 0, 0, 0, 0]
        part["has_cart_activity_30d"] = [1, 1, 0, 0, 0, 0]
        part["has_behavioral_activity_30d"] = [1, 1, 1, 1, 0, 0]
        frames.append(part)
    data = pd.concat(frames, ignore_index=True)
    output = tmp_path / "run"
    real_fit = experiment.fit_models
    calls = []

    def guarded_fit(train):
        assert train.first_purchase_ts.max() < TRAINING_DATE
        models = real_fit(train)
        for name, model in models.items():
            original = model.predict_proba

            def predict(x, original=original, name=name):
                if x.page_views_30d.max() == 30:
                    assert (output / "selection.json").is_file()
                    calls.append(name)
                return original(x)

            model.predict_proba = predict
        return models

    monkeypatch.setattr(experiment, "load_dataset", lambda: (data, "synthetic"))
    monkeypatch.setattr(experiment, "fit_models", guarded_fit)
    monkeypatch.setattr(experiment.joblib, "dump", lambda *args: None)
    result = run_experiment(output)
    assert set(calls) == {"dummy", "logistic", "lightgbm"}
    assert result["splits"]["test"]["customers"] == 6


def test_report_renders_saved_results_without_training():
    from ecommerce_analytics.models.repeat_purchase_report import table

    assert table(["Model", "AP"], [["dummy", 0.1]]) == (
        "| Model | AP |\n| --- | --- |\n| dummy | 0.1 |"
    )
