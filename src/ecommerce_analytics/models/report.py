"""Human-readable baseline evaluation, with frozen protocol and limitations."""

from pathlib import Path

import pandas as pd

from ecommerce_analytics.analytics.behavior_report import markdown_table


def save_report(tables: dict[str, pd.DataFrame], report: Path, output: Path) -> None:
    parts = [
        "# Phase 2.4 — Chronological validation and baseline modeling\n",
        "## Protocol and scope\n",
        "DuckDB remains the validated reference database and is opened read-only. ClickHouse "
        "is the target analytical storage for a later phase; no migration is implemented here. "
        "Only the compact customer feature table is loaded into Pandas, not raw events. "
        "The existing event-based target is unchanged: any purchase in [t, t+14 days), "
        "including purchases in a session already purchasing before the snapshot.\n\n"
        "This is a **provisional baseline**, not a final reliable estimate of deployment "
        "performance. There are only two training dates and one validation/test date each. "
        "A February result cannot establish robustness to seasonality or later cohorts.\n",
        "## Dataset inspection\n",
    ]
    for name in ("feature_schema", "feature_quality", "class_balance", "customer_overlap"):
        parts.extend([f"### {name.replace('_', ' ').capitalize()}\n", markdown_table(tables[name])])
    parts.extend(
        [
            "### Feature distributions by date\n",
            markdown_table(tables["feature_distributions"]),
            "## Chronological validation\n",
            markdown_table(tables["split_summary"]),
            "Training uses November 1 and December 1 only. Validation is January 1; test is "
            "February 1. Training labels end December 15, before January 1; validation labels "
            "end January 15, before February 1. The pipeline asserts strict separation of these "
            "label-window ends from subsequent evaluation dates. There is no random row split "
            "and no retraining on validation before test evaluation.\n\n"
            "Customer overlap is expected for an expanding prior-purchaser cohort. It matches "
            "the intended known-customer use case but does not measure cold-start generalization. "
            "Repeated customers and correlated histories mean rows are not independent. IDs and "
            "prediction dates are excluded from the predictive feature allowlist. Long-lived "
            "sessions cannot leak their future flags because features were computed from "
            "pre-snapshot raw events. Source duplicates, missing-session undercounts, observed "
            "rather than lifetime history, and changing history lengths remain limitations. "
            "This task checks the feature table, not an independent reconstruction of its "
            "upstream temporal provenance; see the Phase 2.3 audit and tests.\n",
            "## Frozen baseline specification\n",
            "Constant: predict the pooled training positive rate for everyone. Logistic: the "
            "ten explicitly allowed historical features, log1p transform for nonnegative skewed "
            "counts/recencies, StandardScaler fitted only on training, and L2 logistic regression "
            "with C=1, lbfgs, max_iter=2000, seed=42, no class weighting. Invalid/missing/infinite "
            "features fail inspection instead of being silently dropped or imputed. Convergence "
            "warnings fail the run. These settings were fixed before any evaluation; no search "
            "or test-based threshold selection is performed.\n\n"
            "Thresholds 0.05, 0.10, 0.20, 0.50 are diagnostic, not selected deployment cutoffs. "
            "Budget fractions 1%, 5%, 10% use K=ceil(n×fraction). Operational score ties are "
            "broken by lexical customer ID solely for deterministic output, never as an input "
            "feature. Tie-expected precision/lift average over random selection within the "
            "cutoff tie, so the constant baseline has expected lift 1.\n",
            "## Validation and test metrics\n",
            "Average Precision is the reported PR summary, not trapezoidal PR-AUC. Higher "
            "ROC-AUC/AP are better; lower Brier/log-loss are better. AP must be compared with "
            "the date-specific prevalence. Confusion matrices are reported as tn/fp/fn/tp. "
            "Precision is reported as zero when a threshold selects nobody, together with the "
            "selected count.\n",
        ]
    )
    for name in ("metrics", "thresholds", "ranking", "calibration"):
        parts.extend([f"### {name.capitalize()}\n", markdown_table(tables[name])])
    parts.extend(
        [
            "Calibration uses ten fixed equal-width bins [a,b), with probability 1 included "
            "in the last bin. Empty bins have missing rates. Compare mean predicted probability "
            "with observed rate in each nonempty bin; ECE weights absolute gaps by bin count. "
            "No recalibration is fitted on validation or test. The constant baseline's calibration "
            "can drift as cohort prevalence changes.\n",
            "## Interpretation\n",
        ]
    )
    for split in ("validation", "test"):
        metrics = tables["metrics"].query("split == @split").set_index("model")
        log, constant = metrics.loc["logistic"], metrics.loc["constant"]
        rank = tables["ranking"].query("split == @split and model == 'logistic'")
        top = rank.iloc[rank.fraction.sub(0.05).abs().argmin()]
        parts.append(
            f"{split.capitalize()}: logistic ROC-AUC {log.roc_auc:.4f}, "
            f"AP {log.average_precision:.4f} versus constant AP {constant.average_precision:.4f}; "
            f"Brier {log.brier_score:.4f} versus {constant.brier_score:.4f}. "
            f"At the fixed top-5% budget, precision is {top.precision_at_k:.2%}, "
            f"lift {top.lift_at_k:.2f}. These are retrospective associations, not evidence "
            "that contacting customers causes purchases. "
            f"Mean predicted probability is {log.mean_probability:.2%} versus observed "
            f"prevalence {log.prevalence:.2%}; the calibration tables quantify this gap.\n"
        )
    parts.extend(
        [
            "## Limitations and next evaluation dates\n",
            "Do not finalize a model from four snapshots. Before another holdout examination, "
            "freeze an expanded rolling-origin protocol. Proposed weekly dates on available "
            "history: November 8/15/22, December 8/15/22, January 8/15/22, and February 8/15. "
            "Only use an earlier snapshot for fitting when its 14-day label window has fully "
            "ended before the evaluation date; overlapping weekly windows require explicit "
            "purging. These dates are proposals, not additional data used in this run. "
            "February 15's label window ends February 29 midnight, within current coverage. "
            "Additional later months should provide a fresh untouched holdout, broader seasonal "
            "coverage and customer-cluster-aware uncertainty estimates. The February snapshot "
            "has now been inspected and cannot serve as an untouched holdout for future tuning. "
            "Define contact cost, capacity and incremental business benefit before selecting an "
            "operating threshold. No such threshold is claimed here.\n",
            "## Coefficients and reproducibility\n",
            "Coefficients are on standardized log1p features, are conditional associations, and "
            "are unstable under correlated counts. No causal interpretation is justified.\n",
            markdown_table(tables["coefficients"]),
            markdown_table(tables["versions"]),
            "```bash\nsource .venv/bin/activate\npython -m pip install -e '.[dev]'\n"
            "python scripts/train_baselines.py\npytest\nruff check .\n"
            "ruff format --check .\n```\n\n"
            "Aggregate CSVs are written to data/processed/phase-2.4/ (ignored by Git). "
            "The CLI accepts --database, --report, --output. No individual predictions or "
            "serialized models are exported, and existing datasets are preserved. The pipeline "
            "refits the same frozen specifications when rerun. Versions above record this run. "
            "No MLflow, LightGBM, deployment or storage migration is included.\n\n"
            "API references: [LogisticRegression](https://scikit-learn.org/stable/modules/generated/"
            "sklearn.linear_model.LogisticRegression.html) and "
            "[Average Precision](https://scikit-learn.org/stable/modules/generated/"
            "sklearn.metrics.average_precision_score.html).\n",
        ]
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(parts), encoding="utf-8")
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False)
