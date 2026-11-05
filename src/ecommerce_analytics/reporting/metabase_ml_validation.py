"""Read-only checks of every dashboard filter combination against frozen evidence."""

import json
import math
from pathlib import Path

from ecommerce_analytics.reporting.metabase_ml import PREFIX, TAB, preserved
from ecommerce_analytics.reporting.ml_results import NOTEBOOK, SCRIPTED, notebook_records

METRICS = {
    "Average Precision (AP)": "average_precision",
    "ROC-AUC": "roc_auc",
    "Lift@10%": "lift_10pct",
    "Brier Score": "brier_score",
}


def validate_dashboard(api, output, dashboard_id=2):
    output = Path(output)
    dashboard = api.request(f"/api/dashboard/{dashboard_id}")
    tabs = [t for t in dashboard["tabs"] if t["name"] == TAB]
    assert len(tabs) == 1
    tiles = [
        dc
        for dc in dashboard["dashcards"]
        if dc["dashboard_tab_id"] == tabs[0]["id"] and dc.get("card_id")
    ]
    assert len(tiles) == 10 and len({dc["card_id"] for dc in tiles}) == 10
    assert len({dc["card"]["name"] for dc in tiles}) == 10
    report = json.loads(
        Path("data/processed/phase-4.1/initial-2026-10-30/metrics.json").read_text()
    )
    notebook = {
        (r["model_name"], r["dataset_split"], r["metric_name"]): r["metric_value"]
        for kind, r in notebook_records(Path("notebooks/01_repeat_purchase_exploration.ipynb"))
        if kind == "metrics"
    }
    results = []
    for experiment, models in [
        (SCRIPTED, ("dummy", "logistic", "lightgbm")),
        (NOTEBOOK, ("logistic", "lightgbm")),
    ]:
        for model in models:
            for split in ("validation", "test"):
                params = [
                    {"id": "ml_" + k, "type": "string/=", "value": [value]}
                    for k, value in dict(experiment=experiment, model=model, split=split).items()
                ]
                n = report["splits"][split]["customers"] if experiment == SCRIPTED else None
                positives = report["splits"][split]["positives"] if n else None
                for dc in tiles:
                    name = dc["card"]["name"].removeprefix(PREFIX)
                    response = api.request(
                        f"/api/dashboard/{dashboard_id}/dashcard/{dc['id']}/card/{dc['card_id']}/query",
                        {"parameters": params},
                    )
                    assert response.get("status") == "completed", (name, response.get("error"))
                    rows = response["data"]["rows"]
                    if name in METRICS:
                        metric = METRICS[name]
                        expected = (
                            report["evaluations"][split][model]["metrics"][metric]
                            if n
                            else notebook.get((model, split, metric))
                        )
                        if expected is None:
                            assert rows == [], (name, rows)
                        else:
                            assert len(rows) == 1 and len(rows[0]) == 1, (name, rows)
                            assert math.isclose(rows[0][0], expected, rel_tol=1e-12, abs_tol=1e-14)
                    elif name == "Feature Importance":
                        available = (experiment == SCRIPTED and model != "dummy") or (
                            experiment == NOTEBOOK and model == "lightgbm"
                        )
                        assert len(rows) == (7 if available else 0), (name, rows)
                        assert len({r[1] for r in rows}) <= 1, "Mixed importance methods"
                    elif n is None:
                        assert rows == [], (name, experiment, rows)
                    elif name == "Scored Customers":
                        assert len(rows) == 1 and rows[0][-1] == n
                    elif name == "Actual Repeat Purchase Rate":
                        assert math.isclose(rows[0][-1], positives / n)
                    elif name == "Actual Repeat Purchase Rate by Score Decile":
                        assert len(rows) == 10 and [r[0] for r in rows] == list(range(1, 11))
                        assert sum(r[1] for r in rows) == n
                        assert max(r[1] for r in rows) - min(r[1] for r in rows) <= 1
                    elif name == "Prediction Probability Distribution":
                        assert sum(r[-1] for r in rows) == n
                    elif name == "Probability Calibration":
                        bins = [
                            b
                            for b in report["evaluations"][split][model]["calibration"]
                            if b["rows"]
                        ]
                        assert len(rows) == len(bins) and sum(r[2] for r in rows) == n
                        for r, b in zip(rows, bins, strict=True):
                            assert r[:3] == [b["lower"], b["upper"], b["rows"]]
                            assert math.isclose(r[3], b["mean_probability"], rel_tol=1e-12)
                            assert math.isclose(r[4], b["observed_rate"], rel_tol=1e-12)
                            assert r[5] == r[3]
                    else:
                        raise ValueError(name)
                    results.append(
                        {
                            "experiment": experiment,
                            "model": model,
                            "split": split,
                            "question": name,
                            "rows": len(rows),
                            "status": "passed",
                        }
                    )
    options = {}
    for exp, expected in [
        (SCRIPTED, {"dummy", "logistic", "lightgbm"}),
        (NOTEBOOK, {"logistic", "lightgbm"}),
    ]:
        value = api.request(
            f"/api/dashboard/{dashboard_id}/params/ml_model/values?ml_experiment={exp}"
        )
        options[exp] = [r[0] for r in value["values"]]
        assert set(options[exp]) == expected
    original = json.loads((output / "before.json").read_text())
    current = {c["id"]: c for c in preserved(dashboard)["cards"]}
    for card in preserved(original)["cards"]:
        assert current[card["id"]] == card, "Preexisting dashboard card changed"
    actual_card_defs = {
        dc["card_id"]: dc.get("card") or {} for dc in dashboard["dashcards"] if dc.get("card_id")
    }
    protected_fields = (
        "name",
        "description",
        "dataset_query",
        "display",
        "visualization_settings",
        "collection_id",
        "parameters",
    )
    for dc in original["dashcards"]:
        if dc.get("card_id"):
            for key in protected_fields:
                assert actual_card_defs[dc["card_id"]].get(key) == dc["card"].get(key), (
                    dc["card_id"],
                    key,
                )
    for tab in original["tabs"]:
        assert tab in dashboard["tabs"]
    for param in original["parameters"]:
        assert param in dashboard["parameters"]
    summary = {
        "query_checks": len(results),
        "results": results,
        "model_filter_options": options,
        "preserved_tabs": len(original["tabs"]),
        "preserved_dashcards": len(original["dashcards"]),
        "managed_question_ids": sorted(dc["card_id"] for dc in tiles),
        "tab_id": tabs[0]["id"],
    }
    (output / "validation.json").write_text(json.dumps(summary, indent=2))
    return {k: v for k, v in summary.items() if k != "results"}
