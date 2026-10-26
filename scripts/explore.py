"""Command-line entry point for full-file exploratory analysis."""

import argparse
import sys
from pathlib import Path

# Support direct execution from a source checkout before an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.analytics.exploration import (  # noqa: E402
    ExplorationError,
    analyze_csv,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Path to a REES46 CSV file")
    args = parser.parse_args(argv)
    try:
        report = analyze_csv(args.input)
    except ExplorationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for title, table in (
        ("Summary", report.summary.T.rename(columns={0: "value"})),
        ("Event types", report.event_types),
        ("Missing values by column", report.missing_values),
        ("Daily event counts (UTC; null dates are missing timestamps)", report.daily_events),
    ):
        print(f"\n{title}\n{'-' * len(title)}")
        print(table.to_string(index=title == "Summary"))
    print(f"\nExact duplicate rows (beyond the first occurrence): {report.duplicate_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
