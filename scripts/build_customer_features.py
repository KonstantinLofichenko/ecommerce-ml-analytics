"""Build Phase 2.3 prior-purchaser snapshots and a validation report."""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.analytics.exploration import ExplorationError  # noqa: E402
from ecommerce_analytics.features.customer_snapshots import (  # noqa: E402
    DEFAULT_SNAPSHOTS,
    build_customer_snapshots,
)
from ecommerce_analytics.features.report import write_feature_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/ecommerce.duckdb"))
    parser.add_argument("--prediction-date", action="append", type=date.fromisoformat)
    parser.add_argument("--report", type=Path, default=Path("docs/reports/phase-2.3-features.md"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/phase-2.3"))
    args = parser.parse_args(argv)
    try:
        if args.report.resolve() == args.database.resolve() or any(
            (args.output / f"{name}.csv").resolve() == args.database.resolve()
            for name in (
                "snapshot_summary",
                "null_checks",
                "feature_statistics",
                "validation",
                "source_quality",
                "label_definition_comparison",
            )
        ):
            raise ExplorationError("Report outputs cannot overwrite the database.")
        tables = build_customer_snapshots(
            args.database,
            prediction_dates=args.prediction_date or DEFAULT_SNAPSHOTS,
            progress=lambda message: print(message, flush=True),
        )
        write_feature_report(tables, args.database, args.report, args.output)
        print(tables["snapshot_summary"].to_string(index=False))
        print(f"Report: {args.report}\nAggregates: {args.output}")
        return 0
    except (ExplorationError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
