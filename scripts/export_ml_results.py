"""Dry-run frozen ML reporting export; publication requires a separate explicit invocation."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecommerce_analytics.ingestion.clickhouse import configured_client, environment  # noqa: E402
from ecommerce_analytics.reporting.ml_results import prepare  # noqa: E402
from ecommerce_analytics.reporting.publication import publish  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts", type=Path, default=Path("data/processed/phase-4.1/initial-2026-10-30")
    )
    parser.add_argument(
        "--notebook", type=Path, default=Path("notebooks/01_repeat_purchase_exploration.ipynb")
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Fresh ignored local package directory"
    )
    parser.add_argument(
        "--publish", action="store_true", help="Explicit write authorization; omit for dry-run"
    )
    parser.add_argument("--database", default="synerise_analytics")
    args = parser.parse_args()
    meta = prepare(args.artifacts, args.notebook, args.output)
    print(json.dumps(meta, indent=2))
    if args.publish:
        print(
            json.dumps(
                publish(configured_client(environment(), "ADMIN"), args.database, args.output)
            )
        )
    else:
        print("DRY RUN: no ClickHouse writes performed")


if __name__ == "__main__":
    main()
