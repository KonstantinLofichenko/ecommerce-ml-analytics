"""Offline checks of ML question definitions; no production API mutations."""

from pathlib import Path

import pytest

from ecommerce_analytics.reporting.metabase_ml import (
    COLUMNS,
    DEFAULTS,
    card_specs,
    preserved,
    query_parameters,
    tables_from_metadata,
)


@pytest.fixture
def specs():
    names = (
        "ml_customer_predictions",
        "ml_experiment_metrics",
        "ml_feature_importance",
        "ml_calibration",
    )
    columns = (
        "export_id",
        *COLUMNS.values(),
        "client_id",
        "actual_target",
        "metric_name",
        "metric_value",
        "prediction_probability",
        "importance_method",
        "importance_value",
        "feature_name",
        "customer_count",
        "mean_predicted_probability",
        "observed_positive_rate",
        "probability_bin_lower",
        "probability_bin_upper",
    )
    tables = {
        name: {"id": n + 1, "fields": {c: (n + 1) * 100 + i for i, c in enumerate(columns)}}
        for n, name in enumerate(names)
    }
    return card_specs(tables, 2, 4, Path("docs/metabase/ml/score-deciles.sql").read_text())


def test_nine_query_builder_questions_one_window_sql(specs):
    assert len(specs) == 10 and len({s["name"] for s in specs}) == 10
    assert sum(s["dataset_query"]["type"] == "query" for s in specs) == 9
    assert specs[6]["dataset_query"]["type"] == "native"
    assert all(s["collection_id"] == 4 for s in specs)


def test_metrics_are_selected_never_aggregated(specs):
    for s in specs[2:6]:
        query = s["dataset_query"]["query"]
        assert "aggregation" not in query
        assert "metric_name" in s["description"] or "Saved" in s["description"]
        assert len(query["fields"]) == 1


def test_required_single_identity_filters(specs):
    for i, s in enumerate(specs):
        assert len(s["parameters"]) == (2 if i == 8 else 3)
        assert all(p["required"] and not p["isMultiSelect"] for p in s["parameters"])
        assert len(query_parameters(s, DEFAULTS)) == len(s["parameters"])


def test_unavailable_prediction_kpis_return_no_groups(specs):
    for s in specs[:2]:
        assert s["dataset_query"]["query"]["breakout"]
    assert specs[0]["visualization_settings"]["scalar.field"] == "count"
    assert specs[1]["visualization_settings"]["scalar.field"] == "avg"


def test_decile_ties_and_scope(specs):
    sql = specs[6]["dataset_query"]["native"]["query"]
    assert "ntile(10)" in sql and "prediction_probability DESC, client_id ASC" in sql
    assert all("{{" + k + "}}" in sql for k in DEFAULTS)


def test_calibration_and_importance_methods(specs):
    assert specs[8]["display"] == "row"
    assert "permutation_validation_ap_drop" in str(specs[8]["dataset_query"])
    assert "standardized_log1p_coefficient" in str(specs[8]["dataset_query"])
    assert "perfect_calibration" in specs[9]["dataset_query"]["query"]["expressions"]


def test_preservation_ignores_card_array_order_only():
    cards = [
        {"id": i, "card_id": i, "row": i, "card": {"dataset_query": {"database": 2}}}
        for i in [2, 1]
    ]
    original = {"tabs": [], "parameters": [], "dashcards": cards}
    other = {**original, "dashcards": cards[::-1]}
    assert preserved(original) == preserved(other)
    other = {**original, "dashcards": [{**cards[0], "row": 99}, cards[1]]}
    assert preserved(original) != preserved(other)


def test_missing_synchronized_views_rejected():
    with pytest.raises(ValueError, match="Missing synchronized"):
        tables_from_metadata({"tables": []})


def test_metric_formatting_uses_supported_column_settings(specs):
    for spec, decimals in zip(specs[2:6], (4, 4, 2, 4), strict=True):
        setting = spec["visualization_settings"]["column_settings"]['["name","metric_value"]']
        assert setting["decimals"] == decimals
        assert setting["number_style"] == "decimal" and setting["scale"] == 1
    assert (
        specs[4]["visualization_settings"]["column_settings"]['["name","metric_value"]']["suffix"]
        == "×"
    )


def test_calibration_has_one_fixed_probability_axis(specs):
    settings = specs[9]["visualization_settings"]
    assert settings["graph.y_axis.auto_split"] is False
    assert settings["graph.y_axis.auto_range"] is False
    assert (settings["graph.y_axis.min"], settings["graph.y_axis.max"]) == (0, 1)
    assert settings["graph.y_axis.scale"] == "linear"
    for column in ("mean_predicted_probability", "observed_positive_rate", "perfect_calibration"):
        setting = settings["column_settings"][f'["name","{column}"]']
        assert setting["number_style"] == "decimal" and setting["scale"] == 1
