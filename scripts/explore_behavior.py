"""Generate the Phase 1.2 customer behavior and session-funnel report."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.analytics.behavior import analyze_behavior  # noqa: E402
from ecommerce_analytics.analytics.behavior_report import save_behavior_report  # noqa: E402
from ecommerce_analytics.analytics.exploration import ExplorationError  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/processed/phase-1.2"))
    parser.add_argument(
        "--report", type=Path, default=Path("docs/reports/phase-1.2-october-2019.md")
    )
    args = parser.parse_args(argv)
    try:
        report = analyze_behavior(args.input, progress=lambda message: print(message, flush=True))
        save_behavior_report(report, args.output, args.report)
    except (ExplorationError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Report: {args.report}\nAggregate CSVs: {args.output}\nSession key: {report.session_key}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
