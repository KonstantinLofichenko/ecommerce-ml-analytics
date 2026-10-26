> Historical archive: this document records an earlier investigation or proposal.
> It does not describe current deployment state. See the [current funnel contract](../../funnel-data-contract.md).

# Phase 3.4.1 — Synerise ingestion benchmark

Measured 21 October 2026 on ClickHouse **25.8.33.6**, Python 3.11.16 and PyArrow 20.0.0.
**INCONCLUSIVE: correctness passed for both formats, but the performance experiment
stopped at a global server-memory error. No ingestion method is approved for the
full historical load.** ArrowStream is the leading candidate for the next controlled
trial, subject to diagnosing tracked-memory pressure at the existing resource limits.

[Scripts and reproduction](../../../analysis/synerise/architecture/benchmark/README.md),
[complete measurements](../../../analysis/synerise/architecture/benchmark/results.json),
[per-trial metrics](../../../analysis/synerise/architecture/benchmark/trials.csv).

## Running configuration and safety

Actual Docker inspection confirmed a healthy `ecommerce-ml-clickhouse-1`,
**8,589,934,592 bytes** container memory, **2,000,000,000 NanoCPUs** (two CPUs).
`system.server_settings` confirmed **6,442,450,944 bytes** server memory. Before
execution, there were no other active queries or background merges, approximately
378.1 GB free disk, 2.64 GB cgroup usage and 1.43 GB resident memory. Limits were
verified live, rather than inferred from files. No service was restarted or changed.

Safety gates required >=2 GiB cgroup headroom, RSS <=4 GiB, disk >=20 GiB and <=8
merges. Each insert used one thread, a 128 MiB query cap, 10,000 rows, synchronous
acknowledgement and no automatic retry. A separate read-only monitoring thread did
not introduce a second writer. **A discovered blind spot was total server tracked
memory:** it can exceed observed RSS. The revised harness additionally gates
`system.metrics.MemoryTracking` at 4 GiB; the original trial samples did not collect
that metric and are not retroactively described as doing so.

## DDL and source preservation

An initial test still failed with code 47: `source_day` ALIAS was unavailable to
`PARTITION BY`. Its database was removed and preservation checks passed. The shared
renderer and commented draft now use `toYYYYMM(tupleElement(event_time_source,1))`
for partitioning and `(client_id,event_time_source,sku/url)` for sorting, omitting
the last field for searches. Tuple order is lexicographic day/second, preserving
civil chronology. There are no ALIAS references in constraints or storage keys.
The corrected six-table schema was then created successfully for both formats.

Twelve fixture round trips (six sources × two formats) preserved full signed Int64
extremes, zero/negative IDs, Unicode and whitespace-bearing vector strings, raw
timestamps, duplicate multiplicities and all five provenance fields. Unexpected
nulls were rejected in both formats for every source. Invalid clocks were rejected;
a separate tiny follow-up independently rejected invalid date, hour and shape.
Fixtures included pre-epoch time, a leap day, midnight and 12 identical repeats
of a purchase record, proving ties and duplicates survive ordinary MergeTree.

Every measured row was checked against the source, including the entire materialized
`Tuple(day Date32,second_of_day UInt32)`, date alias and civil ordinal. Source-clock
strings remain unchanged. This does not verify a timezone, UTC or physical elapsed
time. Downstream SELECTs filtering `source_day` and `source_second` worked on the
actual server; this validates SQL access, not a completed dbt transformation.
Price remains a signed integer bucket, not money. Search/name strings remain strings.

## Comparable workloads and transport

Both methods used original columns, identical destination DDL and the first N rows
of row group 0 in each source. N progressed from 10,000 to 50,000 to 100,000 with
10,000-row requests. All six sources completed both repetitions at 10k and 50k;
execution order was reversed between repetitions. The 100k stage stopped partway
through `product_buy`; `product_properties` 100k was not attempted.

Option A was **HTTP INSERT FORMAT Parquet**, using bounded Snappy Parquet buffers
constructed from source batches. It was not server-side `file()` and did not mount
source data or copy whole files into a volume. Option B read the same source batches
and serialized ArrowStream. Both used existing HTTP transport with gzip level 1.
Source read/decode, payload construction and request durations are recorded separately.
The comparison includes Option A's reencoding cost. Native whole-file or mounted
Parquet performance cannot be inferred from this experiment.

There were **65 completed trials**, **3,140,000 reconciled rows**, and **314 successful
measured requests**. These are repeated sample rows, not unique dataset coverage.
All measured requests have query-log metrics. Each successful trial has zero errors
and retries. The failing request is separately recorded and has no successful-trial
throughput claim. The error log reports 10,000 written rows; failure acknowledgement
was treated as uncertain and the incomplete attempt was never reused or published.

## Measured performance

Balanced 50k workloads comprise 12 trials per method (two per source):

| Method | Total rows | HTTP transfer seconds | Read + preparation + transfer seconds | Aggregate rows/s |
| --- | ---: | ---: | ---: | ---: |
| HTTP Parquet | 600,000 | 0.8123 | 0.9471 | 633,500 |
| ArrowStream | 600,000 | 0.7120 | 0.7739 | 775,269 |

ArrowStream's aggregate pipeline rate was about **22% higher** at 50k. Median rates
per source across the two reversed-order repetitions were:
| Source | HTTP Parquet rows/s | ArrowStream rows/s |
| --- | ---: | ---: |
| page_visit | 818,072 | 937,020 |
| search_query | 506,261 | 608,384 |
| add_to_cart | 645,312 | 844,801 |
| remove_from_cart | 722,317 | 810,981 |
| product_buy | 699,530 | 807,070 |
| product_properties | 530,368 | 742,906 |

These times exclude DDL, reconciliation, Python tuple construction, monitoring,
cleanup and scheduling between requests. Full monitored wall time is also recorded.
At 10k, aggregate pipeline rates were 521,663 vs 614,696 rows/s. The incomplete 100k
stage has nine Parquet and eight ArrowStream successes; it is not a balanced
comparison and is excluded from method selection. Two repetitions and warm caches
are insufficient for confidence intervals or extrapolating full-dataset duration.

## Resource observations and abort

Across completed trials, sampled cgroup usage peaked at **3,293,777,920 bytes
(3.07 GiB)**; sampled server RSS peaked at **2,046,406,656 bytes (1.91 GiB)**.
The Python process sampled RSS peak was **557,039,616 bytes (531 MiB)**, with a
**698,777,600-byte (666 MiB) lifetime high-water mark**. The latter includes
bounded reconciliation, not only Arrow buffers. Samples every approximately 250 ms
plus trial boundaries can miss short spikes and asynchronous metrics can lag.
These are sampled maxima, not proven continuous peaks.

Completed insert query-log peak memory was **22,011,488 bytes (~21 MiB)**. Total
recorded insert CPU was **2.713471 CPU seconds**, from User/SystemTimeMicroseconds.
CPU use is query CPU time, not a continuous container utilization trace. A final
Docker stats sample reported 77.23% CPU (single sample, not an ingestion peak).
Observed merges ranged 0–2. Active parts per completed table ranged **1–35**; event
batches span source months and can create multiple parts. Per-table compressed
bytes, disk bytes and part counts are in the CSV/JSON. Minimum sampled free disk
was **378,238,586,880 bytes**. No merges were disabled, no OPTIMIZE was run, and no
memory limit was increased.

During the first 100k `product_buy` ArrowStream trial, code 241 reported **total
tracked memory would use 6.01 GiB, maximum 6.00 GiB**, with RSS 2.41 GiB. The failing
query's own logged memory was **8,477,680 bytes**. This was the server total limit,
not the 128 MiB query limit. The workload stopped immediately with no insert retry;
remaining comparisons were not attempted. RSS/cgroup samples do not explain the
global tracker spike. Its cause and contributions from background/accounted memory
remain unresolved; this result does not establish ArrowStream-specific causation.
After cleanup, tracked memory recovered to roughly 0.73 GB before tiny recovery tests.

## Reconciliation and recovery

All completed samples passed exact source/destination multiset equality on every
original field. This is stronger than aggregate count equality for these bounded
samples. An order-independent SHA-256 digest over sorted typed-row hashes retains
multiplicity as a reproducible diagnostic. Every row's source filename, file SHA,
archive SHA, release UUID and attempt UUID was checked. The largest measured excess
duplicate count was **16,828** within a 100k sample. No deduplication was applied.

Tiny follow-up live tests used an independently UUID/comment-owned database after
headroom recovered. They passed:

- A real 20-row insert committed, then a client-side ConnectionError discarded its
  acknowledgement. The attempt remained uncertain; replay was refused without a
  second insert, and the table still had exactly 20 rows.
- A changed expected source checksum was rejected before the writer ran; the fresh
  table stayed empty. Original sources were not edited to induce the mismatch.
- A new attempt UUID/table loaded and exactly reconciled the same 20 duplicates.
- Publication guards rejected missing files and uncertain attempts. No production
  publication or exchange was attempted.

This demonstrates the local controller protocol, not durable crash recovery or a
real network fault. Restarting a process mid-request, disk-backed manifests,
cross-host coordination and multi-table atomic publication remain future tests.
Three automated guard tests plus two existing design tests passed. Ruff lint and
format checks passed for the architecture research files.

## Preservation and next step

Both performance databases (initial failed DDL and corrected run) and the separate
recovery database were removed only after exact UUID/comment ownership verification.
Final inspection found no benchmark/recovery databases. REES46 `raw_events` retains
UUID `9242f083-29f7-465e-a9ee-165c03a53f47` and exactly **20,692,840 rows**.
Existing ecommerce/ecommerce_analytics table identities, schemas and metadata row
counts and grants were unchanged. Before/after SHA-256 checks covered the archive,
six source Parquets, DuckDB, Compose, ClickHouse XML, private environment and dbt
files; all protected file comparisons passed. Credential hashes were not exported.
No Metabase connection, Docker volume, AIS resource or service configuration was
changed. No full migration, infrastructure deployment, model training, commit or
push was performed.

ArrowStream has a measured speed advantage and avoids constructing a second Parquet
encoding, while HTTP Parquet also passed correctness without a new mount. Both need
the same file-attempt recovery and reconciliation protocol. **Do not finalize the
transport choice yet:** diagnose total tracked-memory pressure under unchanged 8/6
GiB limits, then review a paced, cleanly monitored rerun of the missing matched 100k
trials and a longer bounded stability test. Only after that evidence supports a GO
should a durable staged loader be implemented. Full 225,224,262-event migration
still requires explicit approval.

Format references: [ClickHouse Parquet input](https://clickhouse.com/docs/reference/formats/Parquet/Parquet)
and [PyArrow bounded Parquet batches](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html).
Live version-specific tests above take precedence over assumptions from current docs.
