"""Provision scoped ingestion/dbt/BI accounts; preserve existing admin and BI connections."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ecommerce_analytics.ingestion.clickhouse import (  # noqa: E402
    MigrationError,
    configured_client,
    environment,
)
from ecommerce_analytics.ingestion.permissions import (  # noqa: E402
    ensure_role_environment,
    provision,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--generate-missing", action="store_true")
    args = parser.parse_args()
    try:
        if args.generate_missing:
            ensure_role_environment(args.env_file)
        values = environment(args.env_file)
        provision(configured_client(values, "ADMIN"), values)
        print("Restricted ingestion, dbt and BI users provisioned; existing credentials unchanged.")
    except MigrationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
