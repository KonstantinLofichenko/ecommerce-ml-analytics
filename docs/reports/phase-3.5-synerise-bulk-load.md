# Phase 3.5 — Synerise native bulk load

**Completed on 22 October 2026.** The permanent `synerise_raw` database contains
**226,758,312 rows**: **225,224,262 behavioral events** and **1,534,050 product-property rows**.
All six post-insert counts match the requested source counts. No errors or retries occurred.

## Destination and measured duration

| Table | Rows | Native insert seconds |
| --- | ---: | ---: |
| `synerise_raw.product_properties` | 1,534,050 | 0.399 |
| `synerise_raw.product_buy` | 2,318,502 | 0.283 |
| `synerise_raw.remove_from_cart` | 2,688,894 | 0.331 |
| `synerise_raw.add_to_cart` | 7,541,117 | 0.816 |
| `synerise_raw.search_query` | 13,223,769 | 2.817 |
| `synerise_raw.page_visit` | 199,451,980 | 26.799 |

Bulk workflow elapsed: **31.489 seconds**; summed INSERT durations:
**31.445 seconds**. Execution interval:
**2026-10-22 02:30:42–02:31:13 UTC** (05:30:42–05:31:13 Moscow time).
Timing excludes preliminary inspection and writing this report.

## Method and validation

The destination did not exist before execution. Six new ordinary MergeTree tables
were created directly in `synerise_raw`, using only the original source columns.
IDs and price buckets remain Int64; timestamps and encoded query/name values remain
String. Properties sort by SKU; events sort by client and original timestamp, with
SKU or URL where applicable. No release metadata, derived clock columns, deduplication
or timestamp conversion was added. Source timezone remains unknown; prices are buckets,
not revenue.

Each file was read with native server-side `file(...,'Parquet',...)` through the
existing read-only source mount. Explicit column lists preserved field mapping.
Each file, including the 199-million-row page file, completed in one INSERT SELECT.
Python sent SQL only; no DuckDB, PyArrow, CSV, JSON event conversion, or data transport
was used.

Validation consisted of `SELECT count()` after each insert and comparing it with
its expected count. The totals above sum those six verified counts. No checksum,
duplicate histogram, distinct-client aggregation, multiset comparison or additional
full-table data-quality scan was run. Count equality does not constitute value-level
reconciliation; this is the explicitly requested minimal acceptance policy.

## Resource settings and preservation

ClickHouse remained healthy with **8 GiB container memory, 6 GiB server memory and
2 CPUs**. Inserts used two threads and a **query-local 4 GiB memory cap**; the
server/container limits were unchanged and remained enabled. Normal reader/insert
block sizes were retained. No custom cgroup/RSS stop threshold or 10k-row batching
was applied. No memory error occurred; no service restart or configuration change
was needed. Peak resource usage was not measured in this simplified run.

REES46 `ecommerce.raw_events` was counted before and after: **20,692,840 rows**.
Existing REES46/analytics and the prior private database tables retained their
UUIDs, schemas and metadata row counts. The private database
`synerise_raw__8efbe3d95dfc431cb1fa66f980f13a67` was neither reused nor deleted.
The original Parquets were read through the existing read-only mount. DuckDB,
Docker volumes, credentials, ports, dbt, Metabase and AIS were not modified.
No dashboards, Kafka, machine learning, commits or pushes were started.

## Execution artifacts

- [Minimal SQL orchestrator](../../analysis/synerise/ingestion/bulk.py)
- [Measured counts, timings and preservation result](../../analysis/synerise/ingestion/bulk-results.json)
- [Executed SQL audit](../../analysis/synerise/ingestion/bulk-executed.sql)

From the repository root, the command used was:

```bash
source .venv/bin/activate
PYTHONPATH=src python analysis/synerise/ingestion/bulk.py --execute
```

This is a one-time import, not an append/retry command. The script refuses to write
when `synerise_raw` already contains tables. Do not replay the audit INSERTs into
populated tables. No cleanup of the prior private database is included.

Ruff lint/format checks passed for the new orchestrator. The live six-file import
and expected counts are the validation for this task. Consumer integration and
any removal of the prior private database remain separate decisions.
