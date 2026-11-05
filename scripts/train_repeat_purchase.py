"""Run the approved, frozen V4.1 chronological repeat-purchase experiment."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.models.repeat_purchase import run_experiment  # noqa: E402
from ecommerce_analytics.models.repeat_purchase_report import write_report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="Fresh ignored experiment directory"
    )
    parser.add_argument("--report", type=Path, help="Optional Markdown aggregate report")
    args = parser.parse_args()
    report = run_experiment(args.output)
    if args.report:
        write_report(args.output / "metrics.json", args.report)
    print("Selected on validation:", report["selection"]["selected_model"])
    for split, models in report["evaluations"].items():
        for name, result in models.items():
            m = result["metrics"]
            print(
                split, name, "AP", round(m["average_precision"], 6), "AUC", round(m["roc_auc"], 6)
            )
    print("Aggregate metrics and model artifacts:", args.output)


if __name__ == "__main__":
    main()
