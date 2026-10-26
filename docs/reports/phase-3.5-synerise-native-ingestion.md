# Phase 3.5 continuation — simplified Synerise native ingestion

Assessed **22 October 2026**. **PARTIALLY COMPLETED; stopped at the cgroup safety
gate.** Four files are fully loaded and validated: **14,082,563 retained rows**, of
which **12,548,513 are events**. The incomplete search attempt was removed;
`page_visit` was not attempted. The full 226,758,312-row acceptance criterion has
not been met. All completed work remains private and intact.

Private database: **`synerise_raw__8efbe3d95dfc431cb1fa66f980f13a67`**.
It contains `product_properties`, `product_buy`, `remove_from_cart`, `add_to_cart`.
No publication pointer, consumer grant, dbt source or Metabase connection was changed.
Read probes confirmed that the restricted BI and dbt accounts cannot select from
this database. The existing administrator remains privileged.

[Scripts and instructions](../../analysis/synerise/ingestion/README.md),
[run manifest](../../analysis/synerise/ingestion/results.json),
[reconciliation values](../../analysis/synerise/ingestion/reconciliation.csv),
[performance measurements](../../analysis/synerise/ingestion/performance.csv).
The prior failed report/results/SQL are preserved under
[history/2026-10-21-failed](../../analysis/synerise/ingestion/history/2026-10-21-failed/).

## Scope and live configuration

This continuation implements the user's revised acceptance policy: **no exact
duplicate histograms, global original-row GROUP BY, or distinct-SKU aggregation**.
Count and independent row-checksum comparisons replace that mandatory gate.
Previously validated six-file native POCs were reused with unchanged source hashes
and DDL; they were not rerun. A targeted synthetic SQL checksum test was independently
checked with Python hashlib, covering signed values, null, empty strings, Unicode
byte lengths and repeated rows. No source event data passed through Python.

Docker was healthy and idle before loading, with the existing source directory
mounted read-only at `/var/lib/clickhouse/user_files/synerise/e90b8fde`. Live limits
were **8 GiB container, 6 GiB server, two CPUs**. Initial tracked memory was about
660 MB, RSS 1.31 GB, cgroup usage 5.15 GB, and free disk about 375.9 GB. Compose,
mounts, credentials, ports and server settings were unchanged; no restart occurred.

Native `file()` reads the original six Parquets; INSERT SELECT writes task-owned
MergeTree tables in a new private release. The existing DDL preserves all original
Int64/String fields and provenance constants, with no DISTINCT or deduplication.
Event timestamps remain original strings plus timezone-naive civil tuples. They
are **not verified UTC**, and prices remain anonymized buckets, not revenue.

## Source identity and count results

The existing archive SHA-256 was freshly verified:
`e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7`.
All six Parquets matched their existing manifest hashes before execution and the
post-run preservation checks. Completed files were also rehashed individually
before being marked complete. Each per-file validation JSON records source hash,
attempt ID, table UUID, schema, checksums and provenance outcome.

| Source | Required | Retained | State |
| --- | ---: | ---: | --- |
| product_properties | 1,534,050 | 1,534,050 | validated |
| product_buy | 2,318,502 | 2,318,502 | validated |
| remove_from_cart | 2,688,894 | 2,688,894 | validated |
| add_to_cart | 7,541,117 | 7,541,117 | validated |
| search_query | 13,223,769 | 0 | failed_unpublished |
| page_visit | 199,451,980 | 0 | not_attempted |

Retained counts were reconfirmed against the actual tables after the stop, along
with their UUIDs. `search_query` had successful June and July INSERT acknowledgements,
but only the June partition finished destination checksum validation. Its entire
incomplete staging table was retired after ownership/quiescence checks. No partial
search rows remain. There is no page table or uncertain append being resumed.

## Independent streaming checksums

Canonical encoding policy **`synerise-row-v2`** includes source name, ordered column
names and logical types, then one null marker or byte-length-prefixed UTF-8 value
per original field. Signed integers use signed decimal text. The SQL expression
and independent Python byte encoder are in `native.py`; reference-test results
are in [encoding-validation.json](../../analysis/synerise/ingestion/encoding-validation.json).

Two separate digest functions operate on every original row:

- Full MD5's 128-bit value is interpreted little-endian and summed into UInt256.
- SHA-256's first 128 bits are independently interpreted and summed into UInt256.
- SHA-256's final 64 bits additionally contribute an order-independent XOR.

Source aggregates read original Parquet values through `file()`; destination
aggregates read actual stored original columns. No expected destination digest
is copied from the source. Row counts, both sums, XOR, null counts, value extrema
and encoded-string byte-length extrema must agree. File-byte SHA-256 is separately
used for source identity and is never compared with a row digest.

All four completed files passed **both digest sums, XOR and exact counts** for
every partition and their combined totals. Full numeric source/destination values
are retained in `reconciliation.csv` and each `*-validation.json`. There were zero
nulls in their original columns and zero incorrect provenance/clock rows.

Event partitions are seven disjoint source months, June–December 2022. Full source
bounds establish coverage; partition counts must sum to the expected full-file
count. Sums and null counts combine by addition, XOR by XOR, and ranges by min/max;
empty partitions are excluded from extrema. No pagination or record-level grouping
is needed. The sums fit UInt256 without overflow at these dataset sizes.

This is strong probabilistic evidence of row-multiset equivalence, including
duplicate multiplicity, **not a mathematical proof**. Exact duplicate histograms
and the formerly mandatory distinct-SKU count were intentionally skipped under
the revised instructions. Neither was silently substituted with an approximate test.

## Source-clock and provenance results

For every row in completed files, the recorded source filename, file/archive hash,
release UUID and attempt UUID matched the validated constants. Original timestamp
min/max and checksum values matched stored strings. Materialized civil dates and
seconds-of-day were verified against those strings. Source-clock bounds were:

| Event file | Minimum | Maximum |
| --- | --- | --- |
| product_buy | 2022-06-23 00:12:15 | 2022-12-08 00:09:15 |
| remove_from_cart | 2022-06-23 00:12:25 | 2022-12-08 00:09:40 |
| add_to_cart | 2022-06-23 00:10:20 | 2022-12-08 00:09:55 |

These are timezone-unverified source times; operational run timestamps below are
explicitly UTC. No transaction or session identifiers were invented, and encoded
search/name vectors were preserved as strings.

## Measured performance and resources

Run interval: **2026-10-22 02:09:03–02:09:37 UTC** (**05:09 Moscow time**),
**33.36 seconds** including initial source verification and the failed search
attempt, excluding final preservation/log collection. Completed-file measurements:

| Source | Insert seconds | Checksum seconds | File elapsed seconds | Insert rows/s | Query peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| product_properties | 0.564 | 1.284 | 1.931 | 2,717,729 | 172.6 |
| product_buy | 1.265 | 2.083 | 3.630 | 1,832,338 | 132.1 |
| remove_from_cart | 1.462 | 2.842 | 4.661 | 1,839,354 | 132.2 |
| add_to_cart | 3.519 | 6.084 | 10.405 | 2,143,177 | 133.9 |

Insert elapsed times include orchestration/gate overhead around the SQL request.
File elapsed intervals start after staging-table creation and include checksum
queries, inserts, provenance, final hash verification and rename. Initial source
hashing and DDL are included only in overall run time. Checksum timing excludes
the separate source-bounds/provenance checks. These are measured smaller-file
results, not a full-page-file throughput estimate.

All **79 executed operations** have naturally flushed query-log records; every SQL
operation completed successfully. The controller stopped before the next search
destination-checksum query. There were **zero SQL errors, zero insert retries**, and
one controller resource stop. Successful file records have per-file query memory,
RSS/cgroup/tracker samples, CPU, parts, compressed/disk bytes and timings.

| Whole-run resource | Observed |
| --- | ---: |
| Peak sampled global tracked memory | 935,236,063 bytes (0.87 GiB) |
| Peak sampled ClickHouse RSS | 2,388,103,168 bytes (2.22 GiB) |
| Peak sampled cgroup usage | 7,060,004,864 bytes (6.58 GiB) |
| Background merges | 0–2 |
| Active release parts | 0–87 |
| Minimum sampled free disk | 375,406,014,464 bytes |

The four validated tables' completion-time disk snapshots total **207,908,710
bytes**; background merges can change physical storage and part counts. Per-table
snapshots are in `performance.csv`, rather than being presented as final immutable
storage sizes. Samples occur about every 0.5 seconds plus operation boundaries;
they can miss spikes and asynchronous memory metrics can lag. Global MemoryTracking
is also recorded before and after every executed operation.

## Exact stop condition and recovery

The reused conservative monitor stops above **6.5 GiB cgroup usage**, above 5 GiB
tracked memory, or below 40 GiB free disk. Between operations it requires cgroup
usage below 6 GiB and tracked memory below 4 GiB, with bounded waiting for headroom.
The search attempt crossed the cgroup threshold at **7,060,004,864 bytes**, while
RSS was 2,388,103,168 bytes and tracked memory only **767,219,004 bytes**.

**This was not a new ClickHouse code 241/global-memory-limit failure.** Removing
record-level aggregation allowed all streaming checks executed here to complete.
The older tracker discrepancy remains unresolved and is not declared fixed.

Post-stop read-only `memory.stat` inspection recorded about **4,001,538,048 bytes
of file cache**, of which **3,986,423,808 were inactive_file**, alongside about
1.08 GB anon. This shows that file cache contributes substantially to current
cgroup usage, but does not reconstruct the exact breakdown at the earlier peak
or justify silently relaxing the threshold. No cache purge, memory-limit increase,
service restart, threshold change or automatic load retry was performed.

The failed search table was verified by exact UUID/comment, quiesced and dropped.
The four validated tables remain untouched in the private release database. No
other file was reloaded or discarded. Publication was refused because two files
remain incomplete; no controlled pointer was written. A later continuation should
reuse these four validated tables and start search with a fresh attempt identity,
not append to the discarded attempt or reload a published dataset.

## Preservation, checks and next step

Fresh before/after checks passed for 17 protected files, existing table identities,
schemas and counts, grants, named volume mappings, memory/CPU settings and other
e-commerce container IDs. REES46 `ecommerce.raw_events` still has exactly
**20,692,840 rows**, UUID `9242f083-29f7-465e-a9ee-165c03a53f47`.
ClickHouse remains healthy. Original Synerise files/archive and DuckDB are unchanged.
Credentials, dbt, Metabase, independent AIS resources and Docker volumes were not
modified. No Kafka, models, commits or pushes were introduced.

**10 local automated tests passed**, covering release acceptance guards, canonical
encoding, associative partition combination, civil-clock DDL and prior recovery
protocols. The independent Python-versus-SQL synthetic digest check passed. Ruff
lint/format and Compose validation passed. Old failed evidence remains archived;
current artifacts clearly label four successful files and the retired search file.

**The full phase remains incomplete.** The next action is to review cgroup total
usage versus reclaimable file cache and establish a measured headroom policy under
the unchanged 8/6 GiB limits. Then explicitly resume the two remaining files while
preserving the four validated tables. Only after all six reconcile should the
release be finalized. No dbt, dashboard, Kafka or ML work should begin from this
partial release.
