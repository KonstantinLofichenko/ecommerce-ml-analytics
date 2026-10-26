"""Markdown and aggregate CSV presentation for Phase 1.2."""

from pathlib import Path

import pandas as pd

from ecommerce_analytics.analytics.behavior import BehaviorReport


def _display(value: object) -> str:
    if pd.isna(value):
        return "—"
    if isinstance(value, float):
        return f"{value:,.0f}" if value.is_integer() else f"{value:,.6f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(frame: pd.DataFrame) -> str:
    """Render tables without introducing an optional tabulate dependency."""
    if frame.empty:
        return "No observations.\n"
    if len(frame.columns) > 6:
        if "approach" in frame.columns or "horizon_days" in frame.columns:
            frame = frame.set_index(frame.columns[0]).T.rename_axis("metric").reset_index()
        elif len(frame) == 1:
            frame = frame.T.rename(columns={frame.index[0]: "value"})
            frame = frame.rename_axis("metric").reset_index()
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separator = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = [
        "| " + " | ".join(_display(v) for v in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows]) + "\n"


def render_behavior_report(report: BehaviorReport) -> str:
    tables = report.tables
    customer = tables["customers"].iloc[0]
    quality = tables["quality"].iloc[0]
    identity = tables["session_identity"].iloc[0]
    duplicate_rows = int(tables["duplicate_event_types"].excess_duplicate_rows.sum())
    raw_funnel = tables["raw_funnel"].set_index("approach")
    strict = raw_funnel.loc["chronological_strict"]
    presence = raw_funnel.loc["presence"]
    parts = [
        "# Phase 1.2 — Customer behavior and funnel exploration\n",
        f"Source: `{report.source}`. All source rows are analyzed. UTC is used throughout.\n",
        "## Measured findings\n",
        f"- {int(quality.events):,} events; {int(customer.customers):,} known customers; "
        f"{int(customer.purchasing_customers):,} purchasing customers.\n"
        f"- {int(customer.multiple_purchasing_sessions):,} customers have multiple recorded "
        f"purchasing sessions; {int(customer.multiple_purchasing_days):,} purchase on multiple "
        "UTC days.\n"
        f"- {int(identity.shared_by_multiple_customers):,} session IDs are shared by multiple "
        f"known customers. Selected session key: `{report.session_key}`; "
        f"{int(quality.raw_unique_session_ids):,} raw session IDs become "
        f"{int(tables['raw_counts'].iloc[0].analytical_sessions):,} analytical sessions.\n"
        f"- {int(quality.excluded_session_events):,} events with missing session IDs are excluded "
        "only from session/funnel metrics, not customer or raw-event counts.\n"
        f"- Presence funnel: {int(presence.view_sessions):,} → {int(presence.cart_sessions):,} → "
        f"{int(presence.purchase_sessions):,} sessions. Strict chronological funnel: "
        f"{int(strict.view_sessions):,} → {int(strict.cart_sessions):,} → "
        f"{int(strict.purchase_sessions):,}.\n"
        f"- {duplicate_rows:,} excess exact duplicate rows; see the scenario comparison below.\n",
    ]
    intervals = tables["purchase_intervals_days"].iloc[0]
    parts.append(
        f"Observed inter-purchasing-session gaps: {int(intervals.observations):,}; "
        f"median {_display(intervals['median'])} days, p90 {_display(intervals.p90)} days.\n"
    )
    if pd.notna(strict.view_to_purchase):
        parts.append(
            f"Strict chronological view-to-purchase conversion is "
            f"{strict.view_to_purchase:.2%} among sessions with a timestamped view; "
            f"presence conversion is {presence.view_to_purchase:.2%} among sessions with a "
            "recorded view.\n"
        )
    for horizon in tables["horizon_feasibility"].itertuples(index=False):
        parts.append(
            f"For {horizon.horizon_days}-day follow-up, "
            f"{horizon.full_followup_anchors:,} purchasing-session anchors have full coverage; "
            f"{horizon.full_followup_anchors_with_repeat:,} have a strictly later repeat within "
            f"the horizon. {horizon.anchors_with_equal_history_and_followup:,} anchors also "
            "have equally long observed history. These are purchaser-only feasibility counts.\n"
        )

    def section(title: str, text: str, names: list[str]) -> None:
        parts.extend([f"## {title}\n", text + "\n"])
        for name in names:
            parts.extend(
                [f"### {name.replace('_', ' ').capitalize()}\n", markdown_table(tables[name])]
            )

    section(
        "1 — Customer behavior",
        "A purchase event is a recorded item-level event, not an "
        "order. A purchasing session contains at least one purchase event; its purchase time "
        "is its first timestamped purchase. A purchasing day is a distinct UTC date per "
        "customer. A purchasing customer has at least one purchase event, including events "
        "with missing session IDs. Unknown customer IDs are excluded from customer metrics. "
        "Purchase-session distributions include a zero bucket for purchasers whose sessions "
        "are all missing. Counts of customer-days and customer-sessions sum per customer, "
        "rather than count purchase events.",
        [
            "customers",
            "purchase_session_frequency",
            "purchase_sessions_distribution",
            "purchase_days_distribution",
        ],
    )
    section(
        "2 — Session behavior",
        f"The raw session-ID audit precedes key selection. "
        f"Observed key: `{report.session_key}`. Shared IDs trigger composite keys for both "
        "scenarios. Missing customer IDs remain in session metrics: under composite keys "
        "they form an unknown-user group; under global keys they retain the recorded session "
        "ID. Such events cannot be attributed to known customers. Session "
        "duration is last minus first observed timestamp, not active engagement time; "
        "single-event sessions have zero duration. Missing timestamps are excluded from "
        "duration bounds and calendar-day counts, and flagged. First/last October-day "
        "sessions are boundary-risk candidates, not proof of complete observation.",
        [
            "session_identity",
            "sessions",
            "event_combinations",
            "events_per_session",
            "products_per_session",
            "duration_seconds",
        ],
    )
    section(
        "3 — Funnel analysis",
        "Both approaches are **session-level, across products**, "
        "not product-level funnels. Presence requires view, then the set {view, cart}, then "
        "the set {view, cart, purchase}, without ordering. Chronological stages require an "
        "observed view, a strictly later cart, and a strictly later purchase. The earliest "
        "view and earliest qualifying cart establish existence of a valid sequence; a wrong "
        "initial order can still be followed by a valid sequence. Equal timestamps never "
        "establish ordering. Tie-dependent counts show additional sessions accepted with "
        "non-strict ordering but excluded by the conservative strict policy. They indicate "
        "ambiguity, not confirmed conversions.\n\n"
        "Rates are fractions in [0, 1]. Stage shares divide by **all eligible sessions**; "
        "view-to-cart and view-to-purchase divide by the approach's view sessions; "
        "cart-to-purchase divides by the approach's qualifying cart sessions. Drop-off is "
        "one minus the corresponding stage conversion; zero denominators yield missing "
        "rates. Raw records are the primary scenario.\n\n"
        "Ordering anomalies count sessions with any timestamped purchase/cart before the "
        "first recorded view. The no-preceding-cart metric counts sessions where the earliest "
        "timestamped purchase has no strictly earlier cart (including ties). Events lacking "
        "timestamps cannot establish order. Timestamp ties count all same-time events within "
        "a selected session; exact identical source-row ties are also reported separately.",
        ["raw_funnel", "ordering_anomalies", "timestamp_ties", "identical_event_timestamp_groups"],
    )
    section(
        "4 — Duplicate analysis",
        "An exact duplicate matches all parsed source columns, "
        "including missing values. Excess rows count multiplicity minus one. Event-type "
        "duplicate percentages divide excess rows by raw rows of that type. Duplicate "
        "multiplicity tables count only groups with multiplicity > 1. Day and session "
        "distributions sum excess rows, with missing session rows reported separately. "
        "The session distribution uses explicit (user_id, user_session) pairs.\n\n"
        "Scenario A preserves all records. Scenario B uses one row per exact group only "
        "in a temporary analytical relation. Neither source files nor a permanent "
        "deduplication policy are changed. Event and purchase-event counts and events-per-"
        "session are sensitive. Distinct customers, sessions, products, event-presence and "
        "existence-based strict funnels should be unchanged by exact duplicates; the "
        "measured side-by-side results below verify this. Timestamp-tie event counts can "
        "also be inflated by duplicates.",
        [
            "duplicate_event_types",
            "duplicate_multiplicity",
            "duplicate_session_summary",
            "duplicate_session_distribution",
            "duplicate_missing_sessions",
            "duplicate_days",
            "scenario_impact",
            "raw_counts",
            "deduplicated_counts",
            "raw_funnel",
            "deduplicated_funnel",
        ],
    )
    section(
        "5 — Purchase frequency and prediction horizons",
        "Intervals are fractional "
        "elapsed days between consecutive known customer purchasing sessions, ordered by "
        "first purchase time. Repeated purchase events within a session do not create "
        "intervals. Missing session/customer IDs and entirely untimestamped purchase "
        "sessions cannot contribute. Tied session starts contribute zero-day intervals; "
        "their internal order is unknowable. Percentiles are continuous; the observations "
        "column counts nonmissing intervals, not customers. Last observed purchasing "
        "sessions are right-censored, not evidence that a customer never returns.\n\n"
        "Horizon feasibility uses each timestamped purchasing session as an exploratory "
        "anchor. Full follow-up requires anchor + horizon ≤ the last observed event; a "
        "repeat must be a distinct session at a strictly later first-purchase time within "
        "the horizon. The next strictly later start is used so tied starts cannot hide a "
        "later repeat. Equal-history-and-follow-up counts additionally require anchor − "
        "horizon ≥ the first observed event. These bounds assume continuous source "
        "coverage, not continuous customer activity. Anchors overlap and come only from "
        "observed purchasers: these are feasibility counts, not final labels or estimates "
        "for all customers. Daily customer-session counts can count a session on more than "
        "one date if it purchases across midnight.",
        [
            "purchase_intervals_days",
            "interval_quality",
            "daily_purchase_activity",
            "horizon_feasibility",
        ],
    )
    section(
        "6 — Data quality and limitations",
        "Source absence is not necessarily behavioral "
        "absence: sessions and prior customer history may start before October, and future "
        "purchases may occur after it. No session is artificially split at midnight. "
        "Outside-October events are retained and counted, not filtered. First and last "
        "observed timestamps bound this file only; completeness and timestamp precision "
        "need upstream confirmation. No secondary order is invented for equal event times. "
        "Missing timestamps remain in presence counts, but cannot advance chronological "
        "stages. Empty CSV fields are missing; whitespace or literal 'NULL' strings remain "
        "source values under the Phase 1.1 convention.\n\n"
        "Missing brand/category metadata is retained and prevents reliable segmentation "
        "without a later documented policy. Unknown sessions/customers prevent attribution. "
        "Shared session IDs may reflect instrumentation issues; composite keys separate "
        "known customers but cannot resolve identity errors. Exact duplicates may reflect "
        "ingestion retries or genuine repeated actions; their cause remains unknown. "
        "Purchase events do not supply order IDs, so order count, basket boundaries, and "
        "true repeat-order frequency cannot be inferred directly.",
        ["quality", "missing_values"],
    )
    parts.extend(
        [
            "## 7 — Recommendations\n",
            "Use the measured 7/14/30-day feasibility counts "
            "to choose an exploratory horizon, balancing repeat support and complete follow-up. "
            "Seven and fourteen days are candidates for further investigation; one October file "
            "cannot support both 30-day feature history and 30-day outcome observation. Add later "
            "months before final horizon selection, labeling, or chronological validation. Repeat "
            "activity supports investigating a customer-level task but does not establish model "
            "usefulness or an adequate positive rate across all customers.\n\n"
            "Confirm session-ID generation, UTC precision, source completeness, order identifiers, "
            "and duplicate provenance with dataset documentation. Retain both duplicate scenarios "
            "until an explicit policy is justified. Next, define observation windows and feature "
            "availability, reserve future time for validation, and compare simple baselines only "
            "after labels and leakage controls are agreed. No model or infrastructure is "
            "introduced "
            "in this phase.\n",
            "## Reproduction\n",
            "From the repository root after installing `.[dev]`:\n\n"
            "```bash\nsource .venv/bin/activate\n"
            f'python scripts/explore_behavior.py --input "{report.source}" '
            "\\\n  --output data/processed/phase-1.2 "
            "\\\n  --report docs/reports/phase-1.2-october-2019.md\n"
            "pytest\nruff check .\nruff format --check .\n```\n\n"
            "All aggregate tables are exported as CSV, including empty tables with headers. "
            "CSV outputs are ignored by Git. The Markdown report records the source path and "
            "definitions. Rerunning replaces generated outputs. No customer-level identifiers "
            "are exported. SQL runs over all rows in DuckDB with a 2 GB working-memory limit, "
            "two threads, and temporary disk spill space; only aggregated results enter Pandas.\n",
        ]
    )
    return "\n".join(parts)


def save_behavior_report(report: BehaviorReport, output: Path, markdown_path: Path) -> None:
    """Save reproducible aggregates and the human-readable report."""
    destinations = [output / f"{name}.csv" for name in report.tables] + [markdown_path]
    source = Path(report.source).resolve()
    if any(path.resolve() == source for path in destinations):
        raise ValueError("An output destination would overwrite the source CSV.")
    output.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    for name, frame in report.tables.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    markdown_path.write_text(render_behavior_report(report), encoding="utf-8")
