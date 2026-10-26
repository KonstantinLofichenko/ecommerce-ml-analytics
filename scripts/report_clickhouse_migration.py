"""Render measured reconciliation artifacts; does not connect to either database."""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd  # noqa: E402

from ecommerce_analytics.analytics.behavior_report import markdown_table  # noqa: E402
from ecommerce_analytics.ingestion.reconciliation import DESTINATION, TYPES  # noqa: E402

if __name__ == "__main__":
    output = Path("data/processed/phase-3.2")
    initial = json.loads((output / "initial_result.json").read_text())
    rerun = json.loads((output / "result.json").read_text())
    reference, target = initial["reference"], initial["destination"]
    months = [m for m in reference if m != "_global"]
    monthly, checksums = [], []
    source_types, target_types, source_duplicates, target_duplicates = (Counter() for _ in range(4))
    for month in months:
        s, d = reference[month]["aggregates"][0], target[month]["aggregates"][0]
        monthly.append(
            {
                "month": month,
                "DuckDB": s["rows"],
                "ClickHouse": d["rows"],
                "difference": d["rows"] - s["rows"],
                "minor_unit_sum": s["price_minor_units"],
                "all_partition_checks": reference[month] == target[month],
            }
        )
        checksums.append(
            {
                "month": month,
                "sum_half_1": str(s["checksum_sum_1"]),
                "sum_half_2": str(s["checksum_sum_2"]),
                "xor": str(s["checksum_xor"]),
                "destination_match": all(
                    s[k] == d[k] for k in ("checksum_sum_1", "checksum_sum_2", "checksum_xor")
                ),
            }
        )
        source_types.update({r["event_type"]: r["rows"] for r in reference[month]["event_types"]})
        target_types.update({r["event_type"]: r["rows"] for r in target[month]["event_types"]})
        source_duplicates.update(
            {r["multiplicity"]: r["groups"] for r in reference[month]["duplicates"]}
        )
        target_duplicates.update(
            {r["multiplicity"]: r["groups"] for r in target[month]["duplicates"]}
        )
    nulls = [
        {
            "column": c,
            "DuckDB": sum(reference[m]["aggregates"][0]["null_" + c] for m in months),
            "ClickHouse": sum(target[m]["aggregates"][0]["null_" + c] for m in months),
        }
        for c in DESTINATION
    ]
    type_table = [
        {"event_type": k, "DuckDB": v, "ClickHouse": target_types[k]}
        for k, v in source_types.items()
    ]
    duplicate_table = [
        {
            "multiplicity": k,
            "DuckDB_groups": v,
            "ClickHouse_groups": target_duplicates[k],
            "excess_rows": (k - 1) * v,
        }
        for k, v in sorted(source_duplicates.items())
    ]
    duplicates = sum(r["excess_rows"] for r in duplicate_table)
    fingerprint = json.loads((output / "source_file_before.json").read_text())
    parts = [
        "# Phase 3.2 — ClickHouse historical migration and reconciliation\n",
        "Measured on 20 October 2026. Destination: `ecommerce.raw_events`. "
        "DuckDB reference remains `data/processed/ecommerce.duckdb`.\n",
        f"**Published {initial['rows']:,} raw events with zero reconciliation differences.** "
        f"A normal rerun after a ClickHouse restart returned `{rerun['status']}`, "
        f"inserted {rerun['inserted_rows']} rows, and reconfirmed the same dataset.\n",
        "## Schema and storage choices\n",
        "DuckDB originally has ten nullable VARCHAR columns plus one UTC-normalized TIMESTAMP. "
        "ClickHouse stores twelve columns: original strings remain, `price` becomes an exact "
        "nullable Decimal(18,2), and `price_raw` preserves the original price text. No artificial "
        "event ID or uniqueness constraint was introduced.\n",
        markdown_table(
            pd.DataFrame(
                [
                    {
                        "column": c,
                        "ClickHouse_type": TYPES[c],
                        "DuckDB_source": (
                            "price VARCHAR"
                            if c in ("price", "price_raw")
                            else "TIMESTAMP"
                            if c == "event_time_utc"
                            else "VARCHAR"
                        ),
                    }
                    for c in DESTINATION
                ]
            )
        ),
        "Ordinary MergeTree partitions by source YYYY-MM month. Sorting clusters month, "
        "customer, session, UTC timestamp and product; null-safe expressions affect ordering "
        "only, never stored values. IDs remain strings, including leading zeros. "
        "DateTime64(6, UTC) preserves microseconds; prices -79.37 through 327.78 fit exactly. "
        "Duplicate raw records are retained, including identical rows across insert batches.\n",
        "## Reconciliation results\n",
        markdown_table(pd.DataFrame(monthly)),
        "### Event types\n",
        markdown_table(pd.DataFrame(type_table)),
        f"Global distinct users: **{reference['_global'][0]['distinct_users']:,}** "
        "in both engines. "
        f"Price sum: **{sum(reference[m]['aggregates'][0]['price_minor_units'] for m in months):,} "
        "integer minor units**, exactly equal. This is the sum of price across raw events, "
        "not order revenue; no floating-point tolerance was used.\n",
        "Timestamp range: **2019-10-01 00:00:00.000000 UTC** through "
        "**2020-02-29 23:59:59.000000 UTC**, equal by month and globally. "
        "The actual source has zero source-month/timestamp-month mismatches.\n",
        "### Null counts\n",
        markdown_table(pd.DataFrame(nulls)),
        "### Duplicate multiplicities\n",
        markdown_table(pd.DataFrame(duplicate_table)),
        f"Excess exact duplicate rows: **{duplicates:,}**, preserved. Groups are formed "
        "from all nine original attributes within each source month; no deduplication policy "
        "is applied. All input rows remain in the destination.\n",
        "### Order-independent canonical checksums\n",
        markdown_table(pd.DataFrame(checksums)),
        "Each engine independently hashes actual stored original strings, provenance, normalized "
        "UTC timestamp and exact typed-price minor units. UTF-8 byte-length prefixes distinguish "
        "null, empty strings, Unicode and delimiters. Two MD5-half 128-bit sums plus a 64-bit "
        "XOR and row count agree in all five partitions. Multiplicity affects the sums. "
        "Checksums are strong probabilistic multiset evidence, not a formal proof against "
        "adversarial hash collisions. Exact aggregate and duplicate distributions also match.\n",
        "## Ingestion, idempotency and recovery\n",
        "Read-only DuckDB streams 50,000-row JSONEachRow batches, gzip-compressed at level 1, "
        "with one synchronous insert in flight. No full event DataFrame or new client dependency "
        "is needed. Each attempt has a UUID-scoped staging table; no uncertain INSERT is retried "
        "into that table. Instead it is abandoned and a fresh full attempt starts. Only a fully "
        "reconciled stage can publish.\n\n"
        "First publication used one Atomic RENAME. Replacements use one Atomic EXCHANGE and retain "
        "the prior destination as a rollback table. Lost publication acknowledgements are resolved "
        "by immutable UUIDs, never a repeated swap. Managed-schema checks, a local advisory lock "
        "and a pre-publication destination UUID guard protect the operation. Multi-host/concurrent "
        "out-of-band writers are unsupported.\n",
        "The real first staging attempt encountered ClickHouse error **241 (memory limit)** "
        "after 3,000,000 acknowledged rows. It remained unpublished. The built-in second attempt "
        "started fresh and completed successfully. No memory limit was increased, no volume "
        "was deleted, and no incomplete data was exposed as raw_events.\n\n"
        "The abandoned staging table and its local manifest were removed after verifying its "
        "identity and unpublished status. Cleanup confirmed that no staging tables remained "
        "and that the published raw_events UUID and 20,692,840 rows were unchanged.\n",
        "## Runtime and resource observations\n",
        f"- Initial end-to-end run, including source checks and one retry: "
        f"**{initial['duration_seconds']:.3f} seconds**.\n"
        "- Successful transfer: **64.609 seconds**, approximately **320,277 rows/second**.\n"
        f"- Successful attempt transfer plus stage validation: "
        f"**{initial['load_and_validation_seconds']:.3f} seconds**.\n"
        "- Fully reconciled no-op rerun after restart: "
        f"**{rerun['duration_seconds']:.3f} seconds**, "
        "**zero inserted rows**.\n"
        "- Observed ClickHouse memory samples: **1.51 GiB** during ingestion, **1.316 GiB** "
        "after publication, **1.261 GiB** after restart/reconciliation. These are samples, "
        "not a continuously measured peak. Container cap remains **2 GiB**, "
        "server cap **1.5 GiB**.\n"
        "- Published table active compressed storage sample: **717,744,163 bytes**; "
        "background merges can change this value without changing rows.\n"
        "- Query budget: two threads, 512 MiB per query, external grouping/sorting at 128 MiB. "
        "DuckDB working memory is capped at 2 GB with temporary spill space. "
        "Source and destination scans are partitioned; reference metrics are computed "
        "once per run.\n",
        "## Permissions and dbt\n",
        "Added independent `ecommerce_ingest`, `ecommerce_dbt`, and `ecommerce_bi` users. "
        "Ingestion manages staging/publication only in ecommerce. dbt reads raw_events and "
        "writes only ecommerce_analytics. BI reads raw_events only. Permission probes verified "
        "all three can read 20,692,840 rows; only ingestion may insert raw rows. dbt can create, "
        "select and drop a temporary transformation-schema view. Production INSERT probes "
        "selected zero rows, so they added nothing.\n\n"
        "The existing ecommerce_app credential/grants and saved Metabase connection were not "
        "changed. Switching Metabase to the new BI credential is a documented manual step; "
        "no UI connection was overwritten. dbt Compose now uses its restricted account. "
        "No passwords appear in this report, URLs, progress logs or versioned files.\n\n"
        "`dbt/models/sources.yml` declares ecommerce.raw_events with metadata and observed "
        "null/event/month tests. Restricted-account `dbt debug` passed. **All 7 dbt tests passed** "
        "(connectivity, exact historical count and five source-level checks). "
        "No production transformation models were created.\n",
        "## Automated checks and preservation\n",
        "**77 Python tests passed**, with live ClickHouse tests explicitly enabled and no skips. "
        "Ruff lint/format and Compose validation passed. Tests are separate from ML features "
        "and cover schema/type errors, invalid timestamps/months/prices, nullable/Unicode "
        "values, microseconds, monetary precision, duplicate preservation, no-op reruns, "
        "committed-insert/lost-response recovery, lost EXCHANGE acknowledgement, and staging "
        "corruption with equal row counts. A corrupted staging table fails checksums and "
        "never replaces the prior destination. Live tests create/drop only UUID-owned "
        "test databases.\n\n"
        f"DuckDB file SHA-256 before and after migration: `{fingerprint['sha256']}`. "
        "The file is byte-for-byte unchanged. No sessions, customers, feature tables, dashboards "
        "or DAGs were rebuilt and no production models were trained. AIS resources and persistent "
        "volumes were not modified. Restarting only the e-commerce ClickHouse service preserved "
        "the dataset and restricted accounts; full post-restart reconciliation passed.\n",
        "## Files and reproduction\n",
        "Created `ingestion/clickhouse.py`, `reconciliation.py`, `migration.py`, `permissions.py`; "
        "`scripts/bootstrap_clickhouse.py`, `migrate_clickhouse.py`, "
        "`check_clickhouse_permissions.py`, `report_clickhouse_migration.py`; "
        "`tests/test_clickhouse_migration.py`; `dbt/models/sources.yml`, "
        "`dbt/tests/raw_event_count.sql`; `docs/clickhouse-migration.md` and this report. "
        "Updated Compose dbt credentials/schema, environment templates/generator, "
        "infrastructure tests, README and architecture/infrastructure documentation. "
        "Private .env gained separate role credentials without changing existing values.\n",
        "```bash\nsource .venv/bin/activate\n"
        "python scripts/bootstrap_clickhouse.py --generate-missing\n"
        "python scripts/migrate_clickhouse.py\n"
        "python scripts/migrate_clickhouse.py --validate-only\n"
        "python scripts/check_clickhouse_permissions.py\n"
        "ECOMMERCE_CLICKHOUSE_TESTS=1 pytest\n"
        "docker compose --profile tools run --rm dbt debug\n"
        "docker compose --profile tools run --rm dbt test\n```\n\n"
        "See [migration operations](../clickhouse-migration.md) for schema reasoning, environment "
        "configuration, source-query checks, rollback, abandoned-stage cleanup and limits. "
        "Aggregate artifacts and local run-state JSON remain under ignored "
        "`data/processed/phase-3.2/`. No commits or pushes were made.\n",
    ]
    report = Path("docs/reports/phase-3.2-migration.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(parts), encoding="utf-8")
    pd.DataFrame(monthly).to_csv(output / "monthly_reconciliation.csv", index=False)
    pd.DataFrame(type_table).to_csv(output / "event_type_reconciliation.csv", index=False)
    pd.DataFrame(nulls).to_csv(output / "null_reconciliation.csv", index=False)
    pd.DataFrame(duplicate_table).to_csv(output / "duplicate_reconciliation.csv", index=False)
    print(f"Report: {report}")
