"""Migrate validated raw DuckDB events through isolated ClickHouse staging."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ecommerce_analytics.ingestion.clickhouse import (  # noqa: E402
    MigrationError,
    configured_client,
    environment,
)
from ecommerce_analytics.ingestion.migration import migrate  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/processed/ecommerce.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/phase-3.2"))
    parser.add_argument("--batch-size", type=int, default=50000)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--expected-rows", type=int, default=20692840)
    parser.add_argument("--force-reload", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--url")
    args = parser.parse_args()
    try:
        if args.force_reload and args.validate_only:
            raise MigrationError("--force-reload and --validate-only cannot be combined.")
        migrate(
            args.source,
            configured_client(environment(), url=args.url),
            args.output,
            args.batch_size,
            args.attempts,
            expected_rows=args.expected_rows,
            force_reload=args.force_reload,
            validate_only=args.validate_only,
        )
    except (MigrationError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
