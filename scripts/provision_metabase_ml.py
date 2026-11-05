"""Add/update the managed ML tab; preserve existing Synerise dashboard components."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ecommerce_analytics.reporting.metabase_ml import Metabase, provision  # noqa: E402
from ecommerce_analytics.reporting.metabase_ml_validation import validate_dashboard  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard", type=int, default=2)
    parser.add_argument("--database", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/processed/metabase-ml/provision"))
    parser.add_argument(
        "--validate-only", action="store_true", help="Read-only dashboard validation"
    )
    args = parser.parse_args()
    if args.validate_only:
        print(validate_dashboard(Metabase(), args.output, args.dashboard))
        raise SystemExit(0)
    cards, _, dashboard = provision(
        Metabase(), args.dashboard, args.database, "docs/metabase/ml/score-deciles.sql", args.output
    )
    print("Dashboard:", dashboard["id"], dashboard["name"])
    print("Questions:", [(c["id"], c["name"]) for c in cards])
