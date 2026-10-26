"""Build the unified October 2019–February 2020 DuckDB dataset and report."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.analytics.behavior_report import markdown_table  # noqa: E402
from ecommerce_analytics.analytics.exploration import ExplorationError  # noqa: E402
from ecommerce_analytics.ingestion.dataset import MONTH_FILES, build_dataset  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--database", type=Path, default=Path("data/processed/ecommerce.duckdb"))
    parser.add_argument(
        "--report", type=Path, default=Path("docs/reports/phase-1.3a-october-2019-february-2020.md")
    )
    parser.add_argument("--output", type=Path, default=Path("data/processed/phase-1.3a"))
    args = parser.parse_args(argv)
    sources = {month: args.raw_dir / filename for month, filename in MONTH_FILES.items()}
    try:
        protected = {path.resolve() for path in sources.values()} | {args.database.resolve()}
        if args.report.resolve() in protected or any(
            (args.output / f"{name}.csv").resolve() in protected
            for name in (
                "monthly_counts",
                "event_type_counts",
                "monthly_event_types",
                "overview",
                "quality_by_month",
                "session_quality",
                "sources",
            )
        ):
            raise ExplorationError("Report outputs would overwrite a source or database.")
        tables = build_dataset(
            sources, args.database, progress=lambda message: print(message, flush=True)
        )
        args.output.mkdir(parents=True, exist_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        parts = [
            "# Phase 1.3A — Unified October 2019–February 2020 dataset\n",
            f"Database: `{args.database}`. All five local CSVs were loaded "
            "without deduplication.\n",
            "## Row counts and duplicate comparison\n",
            "Raw duplicate percentage = (raw rows − exact comparison rows) / raw rows × 100. "
            "Comparison duplicate percentage is zero by construction: the view groups every "
            "original source column, including missing values. Added provenance/parsed-time "
            "columns are not part of exact-row identity. Duplicate groups spanning files are "
            "assigned the earliest source month in the comparison only; raw provenance is "
            "unchanged. Thus monthly removal counts include cross-file duplicate attribution, "
            "not just within-file duplication. No permanent deduplication policy is selected.\n",
        ]
        for name in (
            "overview",
            "monthly_counts",
            "event_type_counts",
            "monthly_event_types",
            "quality_by_month",
            "session_quality",
        ):
            parts.extend(
                [f"### {name.replace('_', ' ').capitalize()}\n", markdown_table(tables[name])]
            )
        parts.extend(
            [
                "## Definitions and exclusions\n",
                "- `raw_events`: original parsed strings plus source `month` (YYYY-MM) "
                "and `event_time_utc` (UTC TIMESTAMP). Empty fields remain NULL; literal NULL or "
                "whitespace strings retain the Phase 1.1 convention. All rows are retained. "
                "Malformed nonempty timestamps or inconsistent column schemas stop and roll back "
                "the build. Missing times and source-month mismatches are retained and reported.\n"
                "- `events_exact_deduplicated`: exact-row comparison view only, "
                "evaluated "
                "over original columns. It does not feed session/customer tables.\n"
                "- `session_summary` / `sessions`: one row per exact "
                "`(user_id, user_session)` pair, represented by a collision-free STRUCT key. "
                "Missing session IDs are excluded here only; unknown customer IDs remain as "
                "explicit NULL-user groups. Start/end and duration use observed UTC times, "
                "not active engagement time. Missing times do not establish order.\n"
                "- Sessions are aggregated across all files, not split at midnight or month end. "
                "`source_months` counts input months; `calendar_months` counts observed "
                "UTC months. "
                "No inactivity timeout is inferred. Reuse of the same pair over a long period "
                "therefore yields one observed session; long sessions need future investigation.\n"
                "- Session funnel flags reuse Phase 1.2 logic, across products. Presence needs "
                "event sets regardless of order; chronological progression requires strictly "
                "increasing view → cart → purchase times. Equal-time sequences cannot prove "
                "order; `tie_dependent_complete` reports additional non-strict completions.\n"
                "- `customer_summary` / `customers`: known customers only, "
                "including their events with missing session IDs. First/last times are observed "
                "UTC bounds, not lifetime history. Total purchasing sessions count distinct "
                "known session IDs per customer, including purchases with missing timestamps.\n"
                "- `customer_monthly_summary` and the five wide monthly count columns "
                "use event UTC month, not source-file month. A purchasing session is counted in "
                "each month where it records a purchase; summing monthly counts can exceed the "
                "distinct-period total. `sessions_first_purchased_in_month` instead assigns a "
                "session once, to its first timestamped purchase month. Missing session IDs "
                "cannot count as purchasing sessions; untimestamped purchases cannot be assigned "
                "to a calendar month and are reported in customer-summary quality columns. "
                "Monthly rows exist only for customer-months with timestamped activity; absent "
                "wide counts are zero, not proof of complete observation.\n"
                "- Dataset boundaries censor earlier history and later behavior; missing recorded "
                "events do not establish behavioral absence. Purchase events are not order IDs. "
                "All primary summaries use raw records, so duplicate events inflate event counts. "
                "Category/brand missing values remain intact. No labels or models are created.\n",
                "## Reproduction and querying\n",
                "```bash\nsource .venv/bin/activate\npython scripts/build_dataset.py\n"
                "pytest\nruff check .\nruff format --check .\n```\n\n"
                "Options: `--raw-dir`, `--database`, `--report`, `--output`. Rebuilding replaces "
                "only the project's named tables/views in the default `main` schema inside one "
                "transaction. A failed build rolls back to the prior dataset; unrelated objects "
                "are retained. The single database file lives under ignored `data/processed/`. "
                "Report CSVs are aggregates and ignored by Git. Source files are read-only. "
                "DuckDB uses 2 GB working memory, two threads, and temporary spill space. "
                "Reserve several GB of free disk. Only aggregates enter Pandas.\n\n"
                "```python\nimport duckdb\n"
                f'with duckdb.connect("{args.database}", read_only=True) as con:\n'
                '    print(con.sql("SELECT month, count(*) FROM raw_events '
                'GROUP BY month ORDER BY month"))\n'
                '    print(con.sql("SELECT * FROM sessions LIMIT 5"))\n'
                "```\n\nUTC timestamps are stored as TIMESTAMP values already normalized to UTC, "
                "so downstream queries need not depend on a connection's local timezone.\n",
                "## Input manifest\n",
                "SHA-256 fingerprints, byte sizes and row counts identify the exact local sources. "
                "Builds use existing CSVs only; no downloads are performed.\n",
                markdown_table(tables["sources"]),
            ]
        )
        args.report.write_text("\n".join(parts), encoding="utf-8")
        print(f"Report: {args.report}\nAggregates: {args.output}")
        for name, table in tables.items():
            table.to_csv(args.output / f"{name}.csv", index=False)
        return 0
    except (ExplorationError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
