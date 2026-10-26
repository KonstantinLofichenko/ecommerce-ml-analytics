# Phase 3.2 — ClickHouse historical migration and reconciliation

Measured on 20 October 2026. Destination: `ecommerce.raw_events`. DuckDB reference remains `data/processed/ecommerce.duckdb`.

**Published 20,692,840 raw events with zero reconciliation differences.** A normal rerun after a ClickHouse restart returned `validated_noop`, inserted 0 rows, and reconfirmed the same dataset.

## Schema and storage choices

DuckDB originally has ten nullable VARCHAR columns plus one UTC-normalized TIMESTAMP. ClickHouse stores twelve columns: original strings remain, `price` becomes an exact nullable Decimal(18,2), and `price_raw` preserves the original price text. No artificial event ID or uniqueness constraint was introduced.

| column | ClickHouse_type | DuckDB_source |
| --- | --- | --- |
| event_time | Nullable(String) | VARCHAR |
| event_type | LowCardinality(Nullable(String)) | VARCHAR |
| product_id | Nullable(String) | VARCHAR |
| category_id | Nullable(String) | VARCHAR |
| category_code | LowCardinality(Nullable(String)) | VARCHAR |
| brand | LowCardinality(Nullable(String)) | VARCHAR |
| price | Nullable(Decimal(18, 2)) | price VARCHAR |
| user_id | Nullable(String) | VARCHAR |
| user_session | Nullable(String) | VARCHAR |
| month | String | VARCHAR |
| event_time_utc | Nullable(DateTime64(6, 'UTC')) | TIMESTAMP |
| price_raw | Nullable(String) | price VARCHAR |

Ordinary MergeTree partitions by source YYYY-MM month. Sorting clusters month, customer, session, UTC timestamp and product; null-safe expressions affect ordering only, never stored values. IDs remain strings, including leading zeros. DateTime64(6, UTC) preserves microseconds; prices -79.37 through 327.78 fit exactly. Duplicate raw records are retained, including identical rows across insert batches.

## Reconciliation results

| month | DuckDB | ClickHouse | difference | minor_unit_sum | all_partition_checks |
| --- | --- | --- | --- | --- | --- |
| 2019-10 | 4102283 | 4102283 | 0 | 3501265832 | True |
| 2019-11 | 4635837 | 4635837 | 0 | 3764624791 | True |
| 2019-12 | 3533286 | 3533286 | 0 | 3134680492 | True |
| 2020-01 | 4264752 | 4264752 | 0 | 3716296825 | True |
| 2020-02 | 4156682 | 4156682 | 0 | 3543923634 | True |

### Event types

| event_type | DuckDB | ClickHouse |
| --- | --- | --- |
| cart | 5768333 | 5768333 |
| purchase | 1287007 | 1287007 |
| remove_from_cart | 3979679 | 3979679 |
| view | 9657821 | 9657821 |

Global distinct users: **1,639,358** in both engines. Price sum: **17,660,791,574 integer minor units**, exactly equal. This is the sum of price across raw events, not order revenue; no floating-point tolerance was used.

Timestamp range: **2019-10-01 00:00:00.000000 UTC** through **2020-02-29 23:59:59.000000 UTC**, equal by month and globally. The actual source has zero source-month/timestamp-month mismatches.

### Null counts

| column | DuckDB | ClickHouse |
| --- | --- | --- |
| event_time | 0 | 0 |
| event_type | 0 | 0 |
| product_id | 0 | 0 |
| category_id | 0 | 0 |
| category_code | 20339246 | 20339246 |
| brand | 8757117 | 8757117 |
| price | 0 | 0 |
| user_id | 0 | 0 |
| user_session | 4598 | 4598 |
| month | 0 | 0 |
| event_time_utc | 0 | 0 |
| price_raw | 0 | 0 |

### Duplicate multiplicities

| multiplicity | DuckDB_groups | ClickHouse_groups | excess_rows |
| --- | --- | --- | --- |
| 1 | 18537980 | 18537980 | 0 |
| 2 | 1011797 | 1011797 | 1011797 |
| 3 | 20576 | 20576 | 41152 |
| 4 | 7319 | 7319 | 21957 |
| 5 | 2199 | 2199 | 8796 |
| 6 | 1442 | 1442 | 7210 |
| 7 | 1123 | 1123 | 6738 |
| 8 | 503 | 503 | 3521 |
| 9 | 318 | 318 | 2544 |
| 10 | 222 | 222 | 1998 |
| 11 | 89 | 89 | 890 |
| 12 | 57 | 57 | 627 |
| 13 | 32 | 32 | 384 |
| 14 | 13 | 13 | 169 |
| 15 | 9 | 9 | 126 |
| 16 | 17 | 17 | 255 |
| 17 | 10 | 10 | 160 |
| 18 | 7 | 7 | 119 |
| 19 | 9 | 9 | 162 |
| 20 | 6 | 6 | 114 |
| 21 | 3 | 3 | 60 |
| 22 | 1 | 1 | 21 |
| 23 | 3 | 3 | 66 |
| 24 | 1 | 1 | 23 |
| 25 | 1 | 1 | 24 |
| 29 | 1 | 1 | 28 |
| 32 | 1 | 1 | 31 |
| 34 | 1 | 1 | 33 |
| 47 | 1 | 1 | 46 |
| 48 | 1 | 1 | 47 |

Excess exact duplicate rows: **1,109,098**, preserved. Groups are formed from all nine original attributes within each source month; no deduplication policy is applied. All input rows remain in the destination.

### Order-independent canonical checksums

| month | sum_half_1 | sum_half_2 | xor | destination_match |
| --- | --- | --- | --- | --- |
| 2019-10 | 37847141830915882216923440 | 37855175350817735445670930 | 5086752053085406188 | True |
| 2019-11 | 42765624769977649879851142 | 42758141777010211778492842 | 1100856910434294862 | True |
| 2019-12 | 32599732245699108060456718 | 32599563543630658152654805 | 7598366067777284142 | True |
| 2020-01 | 39312909644629643772554249 | 39342295784743723621794131 | 4961806521566208541 | True |
| 2020-02 | 38341101637180724455862232 | 38340420249634935230117542 | 17095484034966720696 | True |

Each engine independently hashes actual stored original strings, provenance, normalized UTC timestamp and exact typed-price minor units. UTF-8 byte-length prefixes distinguish null, empty strings, Unicode and delimiters. Two MD5-half 128-bit sums plus a 64-bit XOR and row count agree in all five partitions. Multiplicity affects the sums. Checksums are strong probabilistic multiset evidence, not a formal proof against adversarial hash collisions. Exact aggregate and duplicate distributions also match.

## Ingestion, idempotency and recovery

Read-only DuckDB streams 50,000-row JSONEachRow batches, gzip-compressed at level 1, with one synchronous insert in flight. No full event DataFrame or new client dependency is needed. Each attempt has a UUID-scoped staging table; no uncertain INSERT is retried into that table. Instead it is abandoned and a fresh full attempt starts. Only a fully reconciled stage can publish.

First publication used one Atomic RENAME. Replacements use one Atomic EXCHANGE and retain the prior destination as a rollback table. Lost publication acknowledgements are resolved by immutable UUIDs, never a repeated swap. Managed-schema checks, a local advisory lock and a pre-publication destination UUID guard protect the operation. Multi-host/concurrent out-of-band writers are unsupported.

The real first staging attempt encountered ClickHouse error **241 (memory limit)** after 3,000,000 acknowledged rows. It remained unpublished. The built-in second attempt started fresh and completed successfully. No memory limit was increased, no volume was deleted, and no incomplete data was exposed as raw_events.

The abandoned staging table and its local manifest were removed after verifying its identity and unpublished status. Cleanup confirmed that no staging tables remained and that the published raw_events UUID and 20,692,840 rows were unchanged.

## Runtime and resource observations

- Initial end-to-end run, including source checks and one retry: **141.122 seconds**.
- Successful transfer: **64.609 seconds**, approximately **320,277 rows/second**.
- Successful attempt transfer plus stage validation: **81.167 seconds**.
- Fully reconciled no-op rerun after restart: **69.328 seconds**, **zero inserted rows**.
- Observed ClickHouse memory samples: **1.51 GiB** during ingestion, **1.316 GiB** after publication, **1.261 GiB** after restart/reconciliation. These are samples, not a continuously measured peak. Container cap remains **2 GiB**, server cap **1.5 GiB**.
- Published table active compressed storage sample: **717,744,163 bytes**; background merges can change this value without changing rows.
- Query budget: two threads, 512 MiB per query, external grouping/sorting at 128 MiB. DuckDB working memory is capped at 2 GB with temporary spill space. Source and destination scans are partitioned; reference metrics are computed once per run.

## Permissions and dbt

Added independent `ecommerce_ingest`, `ecommerce_dbt`, and `ecommerce_bi` users. Ingestion manages staging/publication only in ecommerce. dbt reads raw_events and writes only ecommerce_analytics. BI reads raw_events only. Permission probes verified all three can read 20,692,840 rows; only ingestion may insert raw rows. dbt can create, select and drop a temporary transformation-schema view. Production INSERT probes selected zero rows, so they added nothing.

The existing ecommerce_app credential/grants and saved Metabase connection were not changed. Switching Metabase to the new BI credential is a documented manual step; no UI connection was overwritten. dbt Compose now uses its restricted account. No passwords appear in this report, URLs, progress logs or versioned files.

`dbt/models/sources.yml` declares ecommerce.raw_events with metadata and observed null/event/month tests. Restricted-account `dbt debug` passed. **All 7 dbt tests passed** (connectivity, exact historical count and five source-level checks). No production transformation models were created.

## Automated checks and preservation

**77 Python tests passed**, with live ClickHouse tests explicitly enabled and no skips. Ruff lint/format and Compose validation passed. Tests are separate from ML features and cover schema/type errors, invalid timestamps/months/prices, nullable/Unicode values, microseconds, monetary precision, duplicate preservation, no-op reruns, committed-insert/lost-response recovery, lost EXCHANGE acknowledgement, and staging corruption with equal row counts. A corrupted staging table fails checksums and never replaces the prior destination. Live tests create/drop only UUID-owned test databases.

DuckDB file SHA-256 before and after migration: `e2dcf34182f5d8a99add3bbff9133a2ef9ccd34e1069fe9a37fd8580721de9d5`. The file is byte-for-byte unchanged. No sessions, customers, feature tables, dashboards or DAGs were rebuilt and no production models were trained. AIS resources and persistent volumes were not modified. Restarting only the e-commerce ClickHouse service preserved the dataset and restricted accounts; full post-restart reconciliation passed.

## Files and reproduction

Created `ingestion/clickhouse.py`, `reconciliation.py`, `migration.py`, `permissions.py`; `scripts/bootstrap_clickhouse.py`, `migrate_clickhouse.py`, `check_clickhouse_permissions.py`, `report_clickhouse_migration.py`; `tests/test_clickhouse_migration.py`; `dbt/models/sources.yml`, `dbt/tests/raw_event_count.sql`; `docs/clickhouse-migration.md` and this report. Updated Compose dbt credentials/schema, environment templates/generator, infrastructure tests, README and architecture/infrastructure documentation. Private .env gained separate role credentials without changing existing values.

```bash
source .venv/bin/activate
python scripts/bootstrap_clickhouse.py --generate-missing
python scripts/migrate_clickhouse.py
python scripts/migrate_clickhouse.py --validate-only
python scripts/check_clickhouse_permissions.py
ECOMMERCE_CLICKHOUSE_TESTS=1 pytest
docker compose --profile tools run --rm dbt debug
docker compose --profile tools run --rm dbt test
```

See [migration operations](../clickhouse-migration.md) for schema reasoning, environment configuration, source-query checks, rollback, abandoned-stage cleanup and limits. Aggregate artifacts and local run-state JSON remain under ignored `data/processed/phase-3.2/`. No commits or pushes were made.
