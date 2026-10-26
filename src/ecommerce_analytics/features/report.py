"""Aggregate-only reporting for the customer snapshot feature build."""

from pathlib import Path

import pandas as pd

from ecommerce_analytics.analytics.behavior_report import markdown_table
from ecommerce_analytics.features.customer_snapshots import FEATURES


def write_feature_report(
    tables: dict[str, pd.DataFrame], database: Path, report_path: Path, output: Path
) -> None:
    destinations = [report_path, *(output / f"{name}.csv" for name in tables)]
    if any(path.resolve() == database.resolve() for path in destinations):
        raise ValueError("Report outputs cannot overwrite the database.")
    summary = tables["snapshot_summary"]
    discrepancies = summary[summary.reconciliation.str.startswith("DISCREPANCY")]
    comparison = tables["label_definition_comparison"]
    reference = summary.merge(comparison, on="prediction_date")
    definition_note = ""
    if (
        len(reference)
        and reference.expected_positive.notna().all()
        and (reference.expected_positive == reference.new_session_positives).all()
        and (reference.event_target_positives == reference.known_session_positives).all()
    ):
        definition_note = (
            "**Measured finding:** the alternative first-purchase-in-session definition "
            "reproduces every supplied positive count exactly. Additional event-target "
            "positives have future purchases in sessions already purchasing before the "
            "snapshot, without a new purchasing session in the window. Missing session IDs "
            "do not explain these differences. This supports a label-definition mismatch; "
            "the original Phase 2.1 SQL was not available for direct verification. The "
            "requested event-based target is preserved.\n"
        )
    parts = [
        "# Phase 2.3 — Customer-level snapshot features\n",
        f"Database: `{database}`. Analytical table: `customer_snapshot_features`. "
        "No models were trained.\n",
        f"Built **{int(summary.eligible_customers.sum()):,} customer-snapshot rows** with "
        "exactly one row per `(prediction_date, user_id)`. All events and existing analytical "
        "tables are preserved. Only the feature table and its aggregate build audit "
        "are replaced.\n",
        "## Row counts and label distribution\n",
        markdown_table(
            summary[
                [
                    "prediction_date",
                    "eligible_customers",
                    "positive_labels",
                    "negative_labels",
                    "positive_rate",
                ]
            ]
        ),
        "Positive rates are fractions. A row is eligible when a known customer has any "
        "timestamped purchase strictly before midnight UTC on the prediction date, including "
        "purchases with missing session IDs. `target_14d` is 1 for any raw purchase in "
        "[prediction_date, prediction_date + 14 days), else 0. Purchases are recorded events, "
        "not inferred orders or reconstructed session completions.\n",
        "## Reconciliation with supplied Phase 2.1 results\n",
        markdown_table(
            summary[
                [
                    "prediction_date",
                    "expected_eligible",
                    "expected_positive",
                    "eligible_difference",
                    "positive_difference",
                    "reconciliation",
                ]
            ]
        ),
        "All supplied counts match exactly.\n"
        if discrepancies.empty and (summary.reconciliation == "match").all()
        else "Discrepancies or unavailable reference counts are shown explicitly above. "
        "Definitions have not been changed to force agreement. Compare input coverage, "
        "UTC boundaries, prior-purchase eligibility and null-ID handling before proceeding.\n",
        "### Label-definition diagnostic\n",
        markdown_table(tables["label_definition_comparison"]),
        "`new_session_positives` counts eligible customers with a known customer/session "
        "pair whose **first observed purchase** falls in the future 14-day window. "
        "`event_only_positives` captures requested event-target positives without such a "
        "new purchasing session. This alternative is diagnostic only; it does not change "
        "`target_14d`. If event and known-session positives agree, missing session IDs "
        "do not explain the positive-count difference. All session-first timestamps in "
        "this diagnostic are recomputed from raw events and never enter features.\n",
        definition_note,
        "## Historical feature definitions\n",
        markdown_table(pd.DataFrame(FEATURES.items(), columns=["feature", "definition"])),
        "Here t is midnight UTC on `prediction_date`. Every feature uses events strictly "
        "before t. The trailing window is [t − 30 × 24 hours, t); recency uses fractional "
        "elapsed 24-hour days. Historical means all observed data since October 2019, not "
        "the customer's lifetime. Future events are queried separately only for labels. "
        "Whole-session/customer summaries, deduplicated views, and source month fields do "
        "not feed the feature calculations.\n\n"
        "Sessions use exact `(user_id, user_session)` STRUCT keys. Null session IDs never "
        "form a session, but their events still count toward eligibility, targets, recency, "
        "event totals and distinct products. Distinct products exclude null product IDs. "
        "A session straddling a snapshot contributes only its historical events. Its future "
        "purchase may set the target even if the same session also purchased before t: this "
        "is the requested future-purchase-event definition, not a separate-order label. "
        "Raw duplicates remain in event counts; distinct sessions/products are unaffected.\n",
        "## Validation and temporal provenance\n",
        "The feature table has a composite primary key, NOT NULL fields, binary-target and "
        "nonnegative-count checks. Independent raw SQL reconciles the complete sets of "
        "eligible and positive customer keys, not just their counts. Per-snapshot audits "
        "check prior purchases, historical/30-day bounds and label-window bounds. Synthetic "
        "tests additionally perturb future events to verify historical-feature invariance, "
        "and check both inclusive and exclusive boundaries. Zero error counts are required "
        "before committing. Reference-count mismatches are reported, not hidden.\n",
        markdown_table(
            tables["validation"][
                ["prediction_date", *(c for c in tables["validation"] if c.endswith("_errors"))]
            ]
        ),
        "### Observed contributor bounds\n",
        markdown_table(
            tables["validation"][
                [
                    "prediction_date",
                    "latest_feature_event_utc",
                    "earliest_30d_event_utc",
                    "first_label_purchase_utc",
                    "last_label_purchase_utc",
                    "historical_events_missing_session",
                ]
            ]
        ),
        "## Null checks\n",
        markdown_table(tables["null_checks"]),
        "All eligible customers have a timestamped prior purchase, so both recencies are "
        "defined. Count features are zero when there is no matching trailing activity. "
        "No missing recencies are imputed.\n",
        "## Basic feature statistics\n",
    ]
    stats = tables["feature_statistics"]
    for snapshot, frame in stats.groupby("prediction_date", sort=True):
        parts.extend(
            [
                f"### {pd.Timestamp(snapshot).date()}\n",
                markdown_table(frame.drop(columns="prediction_date")),
            ]
        )
    parts.extend(
        [
            "## Source quality and limitations\n",
            markdown_table(tables["source_quality"]),
            "Events with null customer IDs cannot be attributed and are excluded from snapshots. "
            "Untimestamped events cannot establish eligibility, feature windows or labels and are "
            "excluded from those calculations; raw source rows remain untouched. Null session "
            "events are excluded only from session counts. Aggregate quality counts above refer "
            "to the full source; audit null-session counts refer to eligible historical events "
            "per snapshot, so the same event may contribute at multiple dates.\n\n"
            "A build requires the last observed event to reach each target window's exclusive "
            "end. This is a coverage guard, not proof of continuous logging or customer follow-up. "
            "The monthly source is assumed complete between its bounds; unseen purchases are "
            "observed negatives, not proof of no real-world purchase. History is left-censored "
            "at the first source event and January/February customers have more observed history "
            "than November customers. Snapshots repeat customers and overlap historical activity; "
            "later modeling must use temporal validation and avoid treating rows as independent. "
            "Session-ID reuse, duplicate provenance and missing product metadata remain upstream "
            "limitations. No deduplication policy or model split is selected here.\n",
            "## Rebuild and inspect\n",
            "```bash\nsource .venv/bin/activate\npython scripts/build_customer_features.py\n"
            "pytest\nruff check .\nruff format --check .\n```\n\n"
            "Optional `--prediction-date YYYY-MM-DD` arguments replace the default snapshot set. "
            "`--database`, `--report`, and `--output` select existing database and output paths. "
            "Rebuilds replace only the feature and audit tables inside one transaction; failures "
            "restore the prior feature dataset. Do not keep the database open in DBeaver while "
            "building. The existing 2 GB/two-thread DuckDB configuration and temporary spill "
            "directory are reused. Only aggregate results enter Pandas or exported CSV files.\n\n"
            "```python\nimport duckdb\n\n"
            f'with duckdb.connect("{database}", read_only=True) as con:\n'
            "    print(\n        con.sql(\n"
            '            "SELECT prediction_date, count(*), sum(target_14d) "\n'
            '            "FROM customer_snapshot_features GROUP BY 1 ORDER BY 1"\n'
            "        )\n    )\n"
            '    print(con.sql("SELECT * FROM customer_snapshot_features LIMIT 5"))\n'
            "```\n",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(parts), encoding="utf-8")
    for name, frame in tables.items():
        frame.to_csv(output / f"{name}.csv", index=False)
