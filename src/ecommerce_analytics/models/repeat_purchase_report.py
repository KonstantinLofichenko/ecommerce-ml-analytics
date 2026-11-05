"""Render aggregate V4.1 evidence without rerunning training or holdout evaluation."""

import json
from pathlib import Path


def table(headers: list[str], rows: list[list]) -> str:
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(str(value) for value in row) + " |" for row in rows),
        ]
    )


def render_report(report: dict, output: Path) -> str:
    sections = [
        "# V4.1 — Initial chronological repeat-purchase experiment",
        "Executed 30 October 2026. **LightGBM selected using validation Average Precision.** "
        "This is an initial offline experiment, not a deployment or causal inference result.",
        "## Data and maturity policy",
        f"Read-only source: `{report['table']}`. Validated **547,914 unique customers and "
        "74,781 positives**, with no missing/invalid predictors, negative counts or inconsistent "
        "activity flags. Only the seven allowlisted behavioral columns are predictors. IDs, "
        "dates, cohort metadata and target never enter fitting. No source/dbt/Metabase writes.",
        "Target: another purchase on a later represented calendar date, at most 30 dates after "
        "the first observed purchase. A negative label is available at midnight of first-date +31; "
        "the exact maturity boundary is inclusive. This preserves the date target, not 720 hours.",
        table(
            [
                "Split (inclusive dates)",
                "Customers",
                "Positive",
                "Negative",
                "Prevalence",
                "Latest label availability",
            ],
            [
                [
                    label,
                    f"{report['splits'][name]['customers']:,}",
                    f"{report['splits'][name]['positives']:,}",
                    f"{report['splits'][name]['negatives']:,}",
                    f"{report['splits'][name]['prevalence']:.4%}",
                    report["splits"][name]["last_label_available"][:10],
                ]
                for name, label in [
                    ("train", "Train: July 23–August 15"),
                    ("validation", "Validation: September 15–30"),
                    ("test", "Test: November 1–7"),
                ]
            ],
        ),
        "Simulated training: September 15 midnight; model selection: October 31 midnight; "
        "test outcomes evaluated as of December 8 midnight, all under the UTC parsing convention. "
        "Training and validation outcomes are mature before their respective decision dates. "
        "Runtime guards reject unavailable outcomes; no positive-label "
        "exception shortens the embargo.",
        "**313,727 customers excluded** in the August 16–September 14 and October 1–31 temporal "
        "gaps. They are neither training nor evaluation observations. The initial proposed "
        "October boundaries overlapped unavailable outcomes and were "
        "replaced with the approved split.",
        "## Frozen model specification",
        "DummyClassifier uses training prevalence (`strategy='prior'`). Logistic regression uses "
        "log1p followed by StandardScaler fitted only on training, C=1 and max_iter=2000. LightGBM "
        "uses 200 trees, learning_rate=0.05, 15 leaves, max_depth=5, min_child_samples=100, "
        "reg_lambda=1, max_bin=63, one CPU thread, deterministic/force_col_wise enabled. Seed 42. "
        "No class reweighting, resampling, early stopping or hyperparameter search. Models remain "
        "trained on the original training set; there is no validation refit.",
        "Each threshold maximizes **validation F1**, with higher threshold breaking exact ties. "
        "F1 is an exploratory operating-point rule, not an agreed commercial cost function. "
        "Thresholds and the AP-based model choice are saved to selection.json before the first "
        "test prediction. All three frozen models are then evaluated on the holdout; test results "
        "do not select models, parameters or thresholds. Validation "
        "threshold performance is optimistic.",
        "## Overall evaluation",
    ]
    for split in ("validation", "test"):
        sections.append(f"### {split.title()}")
        rows, decisions, matrices = [], [], []
        for name, result in report["evaluations"][split].items():
            m = result["metrics"]
            rows.append(
                [
                    name,
                    *[
                        f"{m[k]:.6f}"
                        for k in [
                            "average_precision",
                            "roc_auc",
                            "lift_10pct",
                            "brier_score",
                            "ece_10_bins",
                        ]
                    ],
                ]
            )
            decisions.append(
                [name, *[f"{m[k]:.6f}" for k in ["threshold", "precision", "recall", "f1"]]]
            )
            matrices.append([name, *[m[k] for k in ["tn", "fp", "fn", "tp"]]])
        sections.extend(
            [
                table(
                    ["Model", "AP (primary)", "ROC-AUC", "Lift@10%", "Brier ↓", "ECE-10 ↓"], rows
                ),
                table(
                    ["Model", "Validation-selected threshold", "Precision", "Recall", "F1"],
                    decisions,
                ),
                table(["Model", "TN", "FP", "FN", "TP"], matrices),
            ]
        )
    sections.extend(
        [
            "Lift uses top ceil(10% × n) scores and tie-expected positives at "
            "the cutoff; this avoids "
            "arbitrary ID ordering making the dummy baseline look useful. "
            "Dummy lift is exactly one. "
            "AP is sklearn Average Precision, not trapezoidal PR area. No "
            "confidence intervals are claimed.",
            "## Calibration diagnostics",
            "No post-hoc calibrator was fitted. Reliability uses ten fixed probability-width bins; "
            "ECE weights absolute bin errors by customer count. Coarse bins can hide local errors. "
            "All bins for every model/split are saved in metrics.json, "
            "alongside Brier and log loss.",
            table(
                ["Split", "Model", "Mean predicted", "Observed rate"],
                [
                    [
                        split,
                        name,
                        f"{r['metrics']['mean_probability']:.6f}",
                        f"{r['metrics']['prevalence']:.6f}",
                    ]
                    for split, models in report["evaluations"].items()
                    for name, r in models.items()
                ],
            ),
            "LightGBM test reliability (nonempty bins):",
            table(
                ["Probability bin", "Customers", "Mean predicted", "Observed rate"],
                [
                    [
                        f"[{b['lower']:.1f}, {b['upper']:.1f}{']' if b['upper'] == 1 else ')'}",
                        b["rows"],
                        f"{b['mean_probability']:.6f}",
                        f"{b['observed_rate']:.6f}",
                    ]
                    for b in report["evaluations"]["test"]["lightgbm"]["calibration"]
                    if b["rows"]
                ],
            ),
            "## Activity-group diagnostics",
            "Groups are disjoint: at least one cart addition; other behavior "
            "including removal-only "
            "activity without additions; no recorded behavior. Each model retains its global "
            "validation-selected threshold. Group lift ranks within that "
            "group, not the global top decile.",
        ]
    )
    for split in ("validation", "test"):
        sections.append(f"### {split.title()} groups")
        sections.append(
            table(
                ["Group", "Customers", "Positive", "Prevalence"],
                [
                    [
                        group,
                        int(r["metrics"]["rows"]),
                        int(r["metrics"]["positives"]),
                        f"{r['metrics']['prevalence']:.4%}",
                    ]
                    for group, r in report["activity_groups"][split]["dummy"].items()
                ],
            )
        )
        sections.append(
            table(
                ["Model", "Group", "AP", "ROC-AUC", "Lift@10%", "Brier", "Precision", "Recall"],
                [
                    [
                        name,
                        group,
                        *[
                            f"{r['metrics'][key]:.6f}"
                            for key in [
                                "average_precision",
                                "roc_auc",
                                "lift_10pct",
                                "brier_score",
                                "precision",
                                "recall",
                            ]
                        ],
                    ]
                    for name, groups in report["activity_groups"][split].items()
                    for group, r in groups.items()
                ],
            )
        )
    total_gain = sum(x["lightgbm_gain"] for x in report["importance"])
    sections.extend(
        [
            "## Feature interpretation",
            table(
                ["Feature", "LR coefficient", "LightGBM gain share", "LightGBM splits"],
                [
                    [
                        x["feature"],
                        f"{x['logistic_standardized_log1p_coefficient']:.6f}",
                        f"{x['lightgbm_gain'] / total_gain:.2%}",
                        x["lightgbm_splits"],
                    ]
                    for x in report["importance"]
                ],
            ),
            f"Logistic intercept: {report['logistic_intercept']:.6f}. Coefficients refer to one "
            "training-standard-deviation change after log1p, including the binary predictors. "
            "Counts and derived flags are correlated; a negative conditional cart-flag coefficient "
            "does not mean cart additions reduce purchasing. Gain importance is training impurity "
            "reduction, not held-out permutation importance or causality. "
            "LightGBM's unused cart flag "
            "is redundant with its cart-count feature.",
            "All no-behavior customers have identical zero feature vectors, so every model assigns "
            "one score within this group: ROC-AUC=0.5 and within-group lift=1. At the selected "
            "thresholds logistic/LightGBM predict no positives in this group. "
            "This is an information "
            "limitation, not an indication that these customers never repeat.",
            "## Limitations and next evaluation",
            "The test covers **seven days**, one retailer, one artifact and one temporal fold. "
            "Seasonality, weekly dependence, drift and sample uncertainty limit generalization. "
            "The 313,727-row exclusion reduces usable training history "
            "substantially. Stronger test "
            "AP for LightGBM is descriptive; no significance or "
            "production-readiness claim is made.",
            "The source timezone and uninterrupted tracking remain **unverified**. Explicit UTC "
            "parsing fixes computation but does not establish physical UTC or "
            "resolve possible DST. "
            "History begins in the archive: first observed purchase is not first-ever acquisition. "
            "Absence of behavior can mean absence of tracking. The date target is not order count. "
            "No synthetic Amazon display fields are predictors.",
            "Recommend obtaining a longer continuous observation period, then "
            "preregistering several "
            "rolling forward folds with labels mature before fitting/model selection, longer final "
            "holdout coverage and temporal uncertainty estimates. Keep a "
            "fresh final holdout for any "
            "future tuning now that these November results are known. This "
            "follow-up is **not implemented**.",
            "## Reproduction and artifacts",
            "Install the pinned runtime (Python 3.11.16 used). On macOS the "
            "LightGBM wheel requires "
            "OpenMP; `brew install libomp` was executed successfully for this run (libomp 23.1.4).",
            "```bash\nuv pip install --python .venv/bin/python -e '.[dev,ml]' "
            "-r requirements/ml-v41.txt\n"
            ".venv/bin/pytest -q tests/test_repeat_purchase.py tests/test_baseline.py\n"
            ".venv/bin/python scripts/train_repeat_purchase.py \\\n"
            "  --output data/processed/phase-4.1/NEW_RUN_DIRECTORY\n```",
            "The CLI uses the project's local .env HTTP credentials, never credential URLs. "
            "Only the existing feature table is read; the full raw-event "
            "dataset is not loaded into "
            "Python. A fresh output directory is mandatory to preserve previous runs. Reproduction "
            "reruns a frozen protocol, not another opportunity to tune against the known test.",
            f"Executed output: `{output}`. It contains `selection.json`, `metrics.json`, and three "
            "joblib models including logistic preprocessing. The directory is Git-ignored; no "
            "customer-level exports or prediction tables are saved. Joblib "
            "artifacts should be loaded "
            "only from trusted sources in the pinned environment.",
            f"Dataset stream SHA-256: `{report['dataset_sha256']}`. "
            f"Elapsed load/fit/evaluation/artifact runtime: "
            f"**{report['elapsed_seconds']:.2f} seconds** "
            "on this machine, excluding package installation and tests. This is not a benchmark.",
            table(
                ["Dependency", "Executed version"], [[k, v] for k, v in report["versions"].items()]
            ),
            f"Python: {report['python']}; platform: `{report['platform']}`. "
            "Exact runtime versions are recorded in `requirements/ml-v41.txt`; platform/native "
            "libraries can affect bit-level results despite fixed seeds.",
        ]
    )
    return "\n\n".join(sections) + "\n"


def write_report(metrics: Path, destination: Path) -> None:
    report = json.loads(metrics.read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_report(report, metrics.parent))
