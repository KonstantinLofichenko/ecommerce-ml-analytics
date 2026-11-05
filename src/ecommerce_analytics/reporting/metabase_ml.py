"""Additive ML dashboard provisioning through the Metabase API; no analytical database writes."""

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ecommerce_analytics.ingestion.clickhouse import environment

TAB = "ML — Repeat Purchase Prediction"
PREFIX = "ML — "
EXPORT = "c498f2518f8708db6ee32c0802b36619a3a44b1b39ba325b4fe5b572422333e7"
DEFAULTS = {"experiment": "v4.1-scripted-2026-10-30", "model": "lightgbm", "split": "test"}
COLUMNS = {"experiment": "experiment_id", "model": "model_name", "split": "dataset_split"}


class Metabase:
    def __init__(self):
        values = environment()
        self.url = values.get("METABASE_URL", "http://127.0.0.1:13000").rstrip("/")
        self.token = None
        self.token = self.request(
            "/api/session",
            {"username": values["METABASE_ADMIN"], "password": values["METABASE_ADMIN_PWD"]},
        )["id"]

    def request(self, path, data=None, method=None):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Metabase-Session"] = self.token
        request = Request(
            self.url + path,
            headers=headers,
            method=method,
            data=None if data is None else json.dumps(data).encode(),
        )
        try:
            with urlopen(request, timeout=180) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            # Do not echo credentials, session responses or submitted user data.
            raise RuntimeError(
                f"Metabase {method or 'POST' if data else 'GET'} {path}: HTTP {exc.code}"
            ) from None


def field(table, name, options=None):
    return ["field", table["fields"][name], options]


def tables_from_metadata(metadata):
    tables = {
        t["name"]: {"id": t["id"], "fields": {f["name"]: f["id"] for f in t["fields"]}}
        for t in metadata["tables"]
        if t.get("schema") == "synerise_analytics"
    }
    for name in (
        "ml_customer_predictions",
        "ml_experiment_metrics",
        "ml_feature_importance",
        "ml_calibration",
    ):
        if name not in tables:
            raise ValueError(f"Missing synchronized reporting view: {name}")
    return tables


def selection_parameters(table, native=False):
    return [
        dict(
            id="ml_" + key,
            name=key.title(),
            slug="ml_" + key,
            type="string/=",
            default=[value],
            required=True,
            isMultiSelect=False,
            target=["variable", ["template-tag", key]]
            if native
            else ["dimension", field(table, COLUMNS[key])],
        )
        for key, value in DEFAULTS.items()
    ]


def card_specs(tables, database, collection, sql):
    p, m, i, c = [
        tables["ml_" + name]
        for name in (
            "customer_predictions",
            "experiment_metrics",
            "feature_importance",
            "calibration",
        )
    ]
    specs = []

    def qb(name, table, display, description, query, settings):
        # Dashboard identity filters are required and single-valued. These saved defaults
        # also make the question's filter intent explicit; never aggregate metric records.
        spec = {
            "name": PREFIX + name,
            "description": "[managed:ml-dashboard-v1] " + description,
            "collection_id": collection,
            "display": display,
            "dataset_query": {
                "database": database,
                "type": "query",
                "query": {
                    "source-table": table["id"],
                    "filter": ["=", field(table, "export_id"), EXPORT],
                    **query,
                },
            },
            "visualization_settings": settings,
            "parameters": selection_parameters(table),
        }
        specs.append(spec)

    qb(
        "Scored Customers",
        p,
        "scalar",
        "Distinct scored customers for one experiment/model/split. Scripted "
        "artifact inference only; notebook unavailable.",
        {
            "aggregation": [["distinct", field(p, "client_id")]],
            "breakout": [field(p, "experiment_id")],
        },
        {"scalar.decimals": 0, "scalar.field": "count"},
    )
    qb(
        "Actual Repeat Purchase Rate",
        p,
        "scalar",
        "Average actual target among the selected scored customers. Later "
        "calendar-date repeat within 30 days; not orders.",
        {
            "aggregation": [["avg", field(p, "actual_target")]],
            "breakout": [field(p, "experiment_id")],
        },
        {"scalar.decimals": 2, "scalar.field": "avg", "scalar.scale": 100, "scalar.suffix": "%"},
    )
    for title, metric, decimals, suffix in [
        ("Average Precision (AP)", "average_precision", 4, ""),
        ("ROC-AUC", "roc_auc", 4, ""),
        ("Lift@10%", "lift_10pct", 2, "×"),
        ("Brier Score", "brier_score", 4, ""),
    ]:
        qb(
            title,
            m,
            "scalar",
            f"Saved {metric} for one experiment/model/split; never averaged. "
            "Notebook values are rounded historical evidence.",
            {
                "filter": [
                    "and",
                    ["=", field(m, "export_id"), EXPORT],
                    ["=", field(m, "metric_name"), metric],
                ],
                "fields": [field(m, "metric_value")],
            },
            {
                "scalar.decimals": decimals,
                "scalar.suffix": suffix,
                "column_settings": {
                    '["name","metric_value"]': {
                        "number_style": "decimal",
                        "decimals": decimals,
                        "scale": 1,
                        "prefix": "",
                        "suffix": suffix,
                    }
                },
            },
        )
    tags = {
        key: {
            "id": "ml-tag-" + key,
            "name": key,
            "display-name": key.title(),
            "type": "text",
            "required": True,
            "default": value,
        }
        for key, value in DEFAULTS.items()
    }
    specs.append(
        {
            "name": PREFIX + "Actual Repeat Purchase Rate by Score Decile",
            "description": "[managed:ml-dashboard-v1] Equal-size rank deciles, "
            "highest scores first. Ties ordered by client_id; differs from tie- "
            "expected saved Lift@10%. Notebook unavailable.",
            "collection_id": collection,
            "display": "bar",
            "dataset_query": {
                "database": database,
                "type": "native",
                "native": {"query": sql, "template-tags": tags},
            },
            "parameters": selection_parameters(p, native=True),
            "visualization_settings": {
                "graph.dimensions": ["score_decile"],
                "graph.metrics": ["actual_repeat_purchase_rate"],
                "graph.x_axis.title_text": "Score decile (1 = highest)",
                "graph.y_axis.title_text": "Actual repeat-purchase rate",
                "column_settings": {
                    '["name","actual_repeat_purchase_rate"]': {"number_style": "percent"}
                },
            },
        }
    )
    qb(
        "Prediction Probability Distribution",
        p,
        "bar",
        "Count of selected customers in 0.05-wide probability intervals. Notebook "
        "has no customer scores.",
        {
            "aggregation": [["count"]],
            "breakout": [
                field(
                    p,
                    "prediction_probability",
                    {"binning": {"strategy": "bin-width", "bin-width": 0.05}},
                )
            ],
        },
        {
            "graph.dimensions": ["prediction_probability"],
            "graph.metrics": ["count"],
            "graph.x_axis.title_text": "Predicted probability (interval width 0.05)",
            "graph.y_axis.title_text": "Customers",
        },
    )
    qb(
        "Feature Importance",
        i,
        "row",
        "Scripted LightGBM gain; notebook validation permutation AP drop; "
        "logistic standardized-log1p coefficients (scripted only). Methods never "
        "combined; importance is not causal. Default scripted LightGBM gain is the summed "
        "training split gain for each feature: raw objective-improvement units, not "
        "a percentage or probability and not normalized. Logistic coefficients and "
        "notebook permutation AP drop retain their own units.",
        {
            "filter": [
                "and",
                ["=", field(i, "export_id"), EXPORT],
                [
                    "or",
                    [
                        "and",
                        ["=", field(i, "experiment_id"), DEFAULTS["experiment"]],
                        [
                            "or",
                            [
                                "and",
                                ["=", field(i, "model_name"), "lightgbm"],
                                ["=", field(i, "importance_method"), "gain"],
                            ],
                            [
                                "and",
                                ["=", field(i, "model_name"), "logistic"],
                                [
                                    "=",
                                    field(i, "importance_method"),
                                    "standardized_log1p_coefficient",
                                ],
                            ],
                        ],
                    ],
                    [
                        "and",
                        ["=", field(i, "experiment_id"), "v4.1-notebook-preserved"],
                        ["=", field(i, "importance_method"), "permutation_validation_ap_drop"],
                    ],
                ],
            ],
            "fields": [
                field(i, k) for k in ("feature_name", "importance_method", "importance_value")
            ],
            "order-by": [["desc", field(i, "importance_value")]],
        },
        {
            "graph.dimensions": ["feature_name"],
            "graph.metrics": ["importance_value"],
            "graph.series_order": [],
            "graph.show_values": True,
            "graph.x_axis.title_text": (
                "Importance (method-specific raw units; default: LightGBM gain)"
            ),
            "graph.y_axis.title_text": "Feature",
            "graph.bar_orientation": "horizontal",
        },
    )
    qb(
        "Probability Calibration",
        c,
        "line",
        "Original scripted equal-width bins; zero-count bins omitted from the "
        "plot only. Observed rate versus mean score; reference is perfect "
        "calibration. No numerical notebook bins available.",
        {
            "filter": [
                "and",
                ["=", field(c, "export_id"), EXPORT],
                [">", field(c, "customer_count"), 0],
            ],
            "expressions": {"perfect_calibration": field(c, "mean_predicted_probability")},
            "fields": [
                field(c, k)
                for k in (
                    "probability_bin_lower",
                    "probability_bin_upper",
                    "customer_count",
                    "mean_predicted_probability",
                    "observed_positive_rate",
                )
            ]
            + [["expression", "perfect_calibration"]],
            "order-by": [["asc", field(c, "probability_bin_lower")]],
        },
        {
            "graph.dimensions": ["mean_predicted_probability"],
            "graph.metrics": ["observed_positive_rate", "perfect_calibration"],
            "graph.x_axis.title_text": "Mean predicted probability",
            "graph.y_axis.title_text": "Observed rate / perfect calibration",
            "graph.y_axis.auto_split": False,
            "graph.y_axis.auto_range": False,
            "graph.y_axis.scale": "linear",
            "graph.x_axis.scale": "linear",
            "graph.y_axis.min": 0,
            "graph.y_axis.max": 1,
            "column_settings": {
                '["name","mean_predicted_probability"]': {
                    "number_style": "decimal",
                    "decimals": 2,
                    "scale": 1,
                },
                '["name","observed_positive_rate"]': {
                    "number_style": "decimal",
                    "decimals": 2,
                    "scale": 1,
                },
                '["name","perfect_calibration"]': {
                    "number_style": "decimal",
                    "decimals": 2,
                    "scale": 1,
                },
            },
        },
    )
    specs[8]["parameters"] = specs[8]["parameters"][:2]
    return specs


def query_parameters(spec, selections):
    return [
        {"type": "category", "target": p["target"], "value": [selections[k]]}
        for k, p in zip(DEFAULTS, spec["parameters"], strict=False)
    ]


def preserved(dashboard):
    """Ignore API view counts/timestamps, preserve actual layouts, queries and filters."""
    keys = (
        "id",
        "card_id",
        "dashboard_tab_id",
        "size_x",
        "size_y",
        "row",
        "col",
        "parameter_mappings",
        "visualization_settings",
        "series",
        "inline_parameters",
        "action_id",
    )
    return {
        "tabs": dashboard["tabs"],
        "parameters": dashboard["parameters"],
        "cards": [
            {**{k: dc.get(k) for k in keys}, "query": (dc.get("card") or {}).get("dataset_query")}
            for dc in sorted(dashboard["dashcards"], key=lambda dc: dc["id"])
        ],
    }


def provision(api, dashboard_id, database_id, sql_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    before = api.request(f"/api/dashboard/{dashboard_id}")
    snapshot = output / "before.json"
    if not snapshot.exists():
        snapshot.write_text(json.dumps(before, indent=2))
    tables = tables_from_metadata(api.request(f"/api/database/{database_id}/metadata"))
    specs = card_specs(tables, database_id, before["collection_id"], Path(sql_path).read_text())
    # Validate every query with explicit default scope before mutating dashboard objects.
    for spec in specs:
        result = api.request(
            "/api/dataset",
            {**spec["dataset_query"], "parameters": query_parameters(spec, DEFAULTS)},
        )
        if result.get("status") != "completed":
            raise ValueError(f"Query failed: {spec['name']}: {result.get('error')}")
    listing = api.request(f"/api/collection/{before['collection_id']}/items?models=card&limit=500")[
        "data"
    ]
    cards = []
    for spec in specs:
        matches = [r for r in listing if r["name"] == spec["name"]]
        if len(matches) > 1:
            raise ValueError("Ambiguous managed question name")
        if matches:
            old = api.request(f"/api/card/{matches[0]['id']}")
            if not (old.get("description") or "").startswith("[managed:ml-dashboard-v1]"):
                raise ValueError("Question name collision with unmanaged content")
            card = api.request(f"/api/card/{old['id']}", spec, "PUT")
        else:
            card = api.request("/api/card/", spec)
        cards.append(card)
    current = api.request(f"/api/dashboard/{dashboard_id}")
    managed_ids = {card["id"] for card in cards}

    def concurrent_snapshot(d):
        state = preserved(d)
        state["cards"] = [c for c in state["cards"] if c["card_id"] not in managed_ids]
        return state

    if concurrent_snapshot(current) != concurrent_snapshot(before):
        raise ValueError("Dashboard changed concurrently; refusing update")
    tabs = [{k: t[k] for k in ("id", "name", "position")} for t in current["tabs"]]
    found = [t for t in tabs if t["name"] == TAB]
    if len(found) > 1:
        raise ValueError("Duplicate ML tabs")
    tab_id = found[0]["id"] if found else -100
    if not found:
        tabs.append({"id": tab_id, "name": TAB, "position": len(tabs)})
    params = [p for p in current["parameters"] if p["id"] not in {"ml_" + k for k in DEFAULTS}]
    for key, value in DEFAULTS.items():
        p = {
            "id": "ml_" + key,
            "name": {"experiment": "Experiment", "model": "Model", "split": "Dataset Split"}[key],
            "slug": "ml_" + key,
            "type": "string/=",
            "sectionId": "string",
            "default": [value],
            "required": True,
            "isMultiSelect": False,
            "values_query_type": "list",
        }
        if key == "model":
            p["filteringParameters"] = ["ml_experiment"]
        if key == "split":
            p["filteringParameters"] = ["ml_experiment", "ml_model"]
        params.append(p)
    managed_ids = {c["id"] for c in cards}
    dc_keys = (
        "id",
        "card_id",
        "dashboard_tab_id",
        "size_x",
        "size_y",
        "col",
        "row",
        "series",
        "parameter_mappings",
        "visualization_settings",
        "inline_parameters",
        "action_id",
    )
    header = next(
        (
            dc
            for dc in current["dashcards"]
            if dc.get("visualization_settings", {})
            .get("text", "")
            .startswith("## ML evidence & availability")
        ),
        None,
    )
    dashcards = [
        {k: dc[k] for k in dc_keys if k in dc}
        for dc in current["dashcards"]
        if dc.get("card_id") not in managed_ids and dc is not header
    ]
    for index, card in enumerate(cards):
        spec = specs[index]
        old = next((dc for dc in current["dashcards"] if dc.get("card_id") == card["id"]), None)
        mappings = []
        for key, p in zip(DEFAULTS, spec["parameters"], strict=False):
            # Importance belongs to training (or notebook validation permutations),
            # independent of evaluation split; do not misleadingly relabel it as test.
            if index == 8 and key == "split":
                continue
            mappings.append(
                {"parameter_id": "ml_" + key, "card_id": card["id"], "target": p["target"]}
            )
        row, col, width, height = (
            (index // 3 * 4, index % 3 * 8, 8, 4)
            if index < 6
            else (
                (8, 0, 12, 7)
                if index == 6
                else (8, 12, 12, 7)
                if index == 7
                else (15, 0, 24, 8)
                if index == 8
                else (23, 0, 24, 8)
            )
        )
        dashcards.append(
            {
                "id": old["id"] if old else -index - 1,
                "card_id": card["id"],
                "dashboard_tab_id": tab_id,
                "row": row + 3,
                "col": col,
                "size_x": width,
                "size_y": height,
                "series": [],
                "parameter_mappings": mappings,
                "visualization_settings": {},
            }
        )
    dashcards.append(
        {
            "id": header["id"] if header else -999,
            "card_id": None,
            "dashboard_tab_id": tab_id,
            "row": 0,
            "col": 0,
            "size_x": 24,
            "size_y": 2,
            "series": [],
            "parameter_mappings": [],
            "visualization_settings": {
                "virtual_card": {
                    "display": "text",
                    "dataset_query": {},
                    "visualization_settings": {},
                },
                "text": "## ML evidence & availability\n"
                "Scripted: **artifact_inference**. Notebook: **saved summaries**; "
                "customer scores/calibration unavailable. Importance does not follow "
                "Dataset Split; method and units are in its question description.",
            },
        }
    )
    api.request(
        f"/api/dashboard/{dashboard_id}",
        {"tabs": tabs, "parameters": params, "dashcards": dashcards},
        "PUT",
    )
    after = api.request(f"/api/dashboard/{dashboard_id}")
    baseline = preserved(before)
    assert [t for t in after["tabs"] if t["name"] != TAB] == [
        t for t in baseline["tabs"] if t["name"] != TAB
    ]
    assert [p for p in after["parameters"] if p["id"] not in {"ml_" + k for k in DEFAULTS}] == [
        p for p in baseline["parameters"] if p["id"] not in {"ml_" + k for k in DEFAULTS}
    ]
    original_cards = [
        c
        for c in baseline["cards"]
        if c.get("card_id") not in managed_ids
        and not c.get("visualization_settings", {})
        .get("text", "")
        .startswith("## ML evidence & availability")
    ]
    managed_header_id = next(
        dc["id"]
        for dc in after["dashcards"]
        if dc.get("visualization_settings", {})
        .get("text", "")
        .startswith("## ML evidence & availability")
    )
    actual_cards = [
        c
        for c in preserved(after)["cards"]
        if c.get("card_id") not in managed_ids and c["id"] != managed_header_id
    ]
    assert sorted(actual_cards, key=lambda c: c["id"]) == sorted(
        original_cards, key=lambda c: c["id"]
    ), "Existing dashboard cards changed"
    (output / "after.json").write_text(json.dumps(after, indent=2))
    return cards, specs, after
