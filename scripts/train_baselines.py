"""Run the frozen Phase 2.4 chronological baseline evaluation."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.analytics.exploration import ExplorationError  # noqa: E402
from ecommerce_analytics.models.baseline import run_baselines  # noqa: E402
from ecommerce_analytics.models.report import save_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/processed/ecommerce.duckdb"))
    parser.add_argument("--report", type=Path, default=Path("docs/reports/phase-2.4-baselines.md"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/phase-2.4"))
    args = parser.parse_args(argv)
    try:
        if args.report.resolve() == args.database.resolve() or args.output.resolve() == (
            args.database.resolve()
        ):
            raise ExplorationError("Output cannot overwrite the source database.")
        print(
            "Inspecting snapshots; fitting frozen baselines on November/December only", flush=True
        )
        tables = run_baselines(args.database)
        if any(
            (args.output / f"{name}.csv").resolve() == args.database.resolve() for name in tables
        ):
            raise ExplorationError("Output cannot overwrite the source database.")
        save_report(tables, args.report, args.output)
        print(tables["metrics"].to_string(index=False))
        print(f"Report: {args.report}")
        return 0
    except (ExplorationError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
