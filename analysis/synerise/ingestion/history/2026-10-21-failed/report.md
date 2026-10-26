# Phase 3.5 — Synerise native ClickHouse ingestion

**NOT COMPLETED — blocked by the existing 6 GiB global memory-tracker failure.**
All six genuine native `file()` POCs passed. The full product-properties insert
passed row-count and all-field checksum checks, but destination duplicate
reconciliation triggered ClickHouse code 241. Execution stopped; its incomplete
attempt and empty release database were removed. **Zero Synerise rows are retained
or published.** No further load was attempted and no resource limit was increased.

[Reproduction and scripts](../../analysis/synerise/ingestion/README.md),
[aggregate results](../../analysis/synerise/ingestion/results.json),
[executed SQL audit](../../analysis/synerise/ingestion/executed.sql),
[failed file manifest](../../analysis/synerise/ingestion/product_properties-validation.json).

## Configuration and preservation

The only service configuration change is one ClickHouse bind mount in `compose.yaml`:

```yaml
- ./data/external/synerise/source:/var/lib/clickhouse/user_files/synerise/e90b8fde:ro
```

Compose resolves the host source to
`/Users/konstantinlofichenko/GitHub/ecommerce-ml-analytics/data/external/synerise/source`.
The server's actual configured `user_files_path` is `/var/lib/clickhouse/user_files/`.
No sources were copied to Docker storage. Resolved Compose validation passed.
Named data/log volumes were inspected before recreation; queries, merges and
mutations were idle at the preservation gate. Only the ClickHouse service was
recreated with `--no-deps --force-recreate`. Its data/log volume names and mappings
were unchanged; the new bind was verified read-only and accessible by native SQL.

ClickHouse 25.8.33.6 is healthy. Live limits remain **8,589,934,592 bytes container**,
**6,442,450,944 bytes server**, and **two CPUs**. No port, credential, server XML,
independent AIS resource, dependency container, existing dbt model or Metabase
connection was changed. No Docker volume or source file was deleted or modified.

Fresh SHA-256 checks verified the existing archive
`e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7`
and all six files against the existing download manifest. Before/after checks of
17 protected files passed, including the archive, Parquets, DuckDB, private .env,
ClickHouse XML and dbt files. Credential hashes were kept private. Existing table
UUIDs, schemas, metadata row counts, grants and non-ClickHouse e-commerce container
IDs were unchanged. REES46 retains UUID
`9242f083-29f7-465e-a9ee-165c03a53f47` and an exact **20,692,840 rows**.

## Native POC and schema

Six dedicated POC tables in the UUID-owned private database each loaded **10,000
rows directly from server-side `file(...,'Parquet',...)`** using INSERT SELECT.
No Python event serialization, HTTP Parquet upload, PyArrow or DuckDB was used.
Both-direction `EXCEPT ALL` comparisons returned zero mismatches for every source;
count, two hash sums, XOR, null and value-range/byte-length checks also agreed.
Duplicates and equal timestamps participate in those comparisons with multiplicity.
All sampled source-clock tuple values and provenance fields matched.

The implementation reuses the corrected Phase 3.4 renderer without changing its
raw schema. Original signed Int64 fields remain signed; original timestamp,
search-vector and name-vector fields remain String. The native samples' observed
client minima were positive; this run does not claim a fresh negative/extreme-ID
fixture beyond the earlier schema validation. The six raw schemas are:

| Table | Original columns |
| --- | --- |
| page_visit | client_id Int64, timestamp String, url Int64 |
| search_query | client_id Int64, timestamp String, query String |
| add_to_cart / remove_from_cart / product_buy | client_id Int64, timestamp String, sku Int64 |
| product_properties | sku Int64, category Int64, price Int64, name String |

Each table also stores source filename, source/archive SHA-256, release UUID and
attempt UUID. Event tables materialize a naive civil `(Date32,UInt32)` tuple and
expose source-day/ordinal aliases, preserving exact source timestamp text without
attaching UTC. Ordinary MergeTree preserves raw duplicates. Corrected keys use the
materialized tuple directly; no order/session IDs, replacement engine or dedup policy
was introduced. Prices are anonymized buckets, never interpreted as revenue.
Source Nullable fields are read explicitly; the destination remains the previously
validated nonnullable schema with unexpected-null default coercion disabled.

## Full-load progress

| Source | Required rows | Full-load rows transiently inserted | Fully validated and retained |
| --- | ---: | ---: | --- |
| product_properties | 1,534,050 | 1,534,050 | No — discarded after failed reconciliation |
| product_buy | 2,318,502 | Not attempted | No |
| remove_from_cart | 2,688,894 | Not attempted | No |
| add_to_cart | 7,541,117 | Not attempted | No |
| search_query | 13,223,769 | Not attempted | No |
| page_visit | 199,451,980 | Not attempted | No |

The 60,000 POC rows were separate temporary comparisons, all removed. They are not
historical-load progress. No event-file full insert started. Expected totals remain
225,224,262 events and 226,758,312 rows including properties; these are not destination
counts achieved by this run.

The full properties count was **1,534,050** in source and destination. Both hashes
and XOR matched exactly:

| Check | Source and destination |
| --- | --- |
| MD5 first-half UInt256 sum | 14154410972357200600205718 |
| MD5 second-half UInt256 sum | 14138565822687717988057930 |
| First-half XOR | 7722948013661045928 |
| Null counts, all original columns | 0 |
| SKU range | 0–1,623,140 |
| Category range | 0–6,988 |
| Price bucket range | 0–99 |
| Name-vector byte lengths | 49–65 |

Hashes encode all original fields using null tags and UTF-8 byte-length prefixes;
order-independent sums retain multiplicity. This is probabilistic multiset evidence,
not a substitute for the failed exact duplicate-histogram gate. Source duplicate
aggregation completed; destination aggregation failed. The later explicit distinct
SKU check was therefore **not reached**, so 1,534,050 distinct SKUs was not freshly
verified in the destination. No file was marked complete merely because its hashes
matched. Full-event min/max/null/duplicate audits remain unexecuted in this phase.

## Resource observations and exact blocker

The run started **2026-10-21 18:00:51 UTC**, stopped **18:01:03 UTC**, and took
**12.19 seconds**, excluding mount preparation and final preservation checks.
Properties source audit took 0.41 seconds, native insertion 0.57 seconds (about
2.7 million rows/s for that insert only), destination audit 0.41 seconds, source
duplicate aggregation 1.37 seconds, and failed destination duplicate aggregation
0.75 seconds. This is not validated end-to-end throughput or a full-load forecast.

One writer/query used one thread, a 512 MiB query cap, 64 MiB external grouping/sort
thresholds, 10k native read blocks and 100k-row/16 MiB insert squashing targets.
Between operations, gates checked tracked memory, cgroup usage, disk and merges;
a separate monitor sampled every approximately 0.5 seconds and could kill only the
currently task-owned query. No global merge controls or OPTIMIZE were used.

Across 65 resource observations:

| Metric | Observed |
| --- | ---: |
| Maximum sampled tracked server memory | 5,496,485,559 bytes (5.12 GiB) |
| Maximum sampled resident memory | 1,819,267,072 bytes (1.69 GiB) |
| Maximum sampled cgroup memory | 3,087,151,104 bytes (2.88 GiB) |
| Minimum observed free disk | 377,763,717,120 bytes |
| Background merges | 0–2 |
| Active task-owned parts | 0–11 |
| Logged operation CPU time | 3.869092 CPU seconds |

All 41 operation IDs have naturally flushed query-log records. Sampled maxima can
miss short peaks. The error itself reports **total tracked memory would use 6.00
GiB; maximum 6.00 GiB**, RSS 1.33 GiB, while executing `AggregatingTransform`.
The failed query's own memory was **79,080,684 bytes**, with zero written rows.
Thus this was a **global server tracker** failure during reconciliation, not a
512 MiB query-cap failure or a native-reader failure. It reproduces the mismatch
between global tracked and resident memory seen in Phase 3.4.1. The root cause is
unresolved; raising the limit or switching transports would not establish a fix.

The sampled tracker crossed the 5 GiB stop threshold. No further operation/load was
attempted after the failed reconciliation. The incomplete file was not retried.
Per-file compressed storage was not captured before its removal; active part count
and free disk were observed, but no final release storage size is claimed. After
cleanup, tracked memory was approximately 0.78 GB and the server remained healthy.

## Recovery, publication and remaining work

Release ID: `9064d433-bbc1-4f79-9a19-2294a01f0320`. Its database was private and had no
new consumer grants. On failure, the query was quiesced, the incomplete properties
table's UUID was verified, and only that owned table was dropped. The now-empty
release database was subsequently removed after verifying its UUID and ownership
comment. No wildcard DROP, source cleanup, production replacement or retry occurred.
No publication pointer, consumer source, dashboard or workflow was switched.

Three new local tests reject incomplete/unverified/wrong-count releases and unknown
source paths. Together with the five existing design/recovery tests, **8 tests
passed**. Ruff lint/format and Compose checks passed. Reproducible scripts, aggregate
results, the failed file manifest and SQL audit are under `analysis/synerise/ingestion/`.
No dependencies, models, Kafka components, commits or pushes were introduced.

**Continuation is NO-GO until the global tracker discrepancy is diagnosed.** The
next step is a focused ClickHouse memory-accounting investigation at the existing
8/6 GiB limits, followed by a controlled reconciliation retest. Only then should a
fresh native file attempt resume under reviewed gates. The planned full event load
uses disjoint source-month predicates, never unstable LIMIT/OFFSET pagination, and
retains data privately until all six files reconcile. No full migration completion,
fully validated private release or safe publication is claimed from this attempt.
