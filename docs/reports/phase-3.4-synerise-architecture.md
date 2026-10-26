# Phase 3.4 — Synerise → ClickHouse architecture

Designed 21 October 2026. **CONDITIONAL GO for staged implementation**, beginning
with a successful resource-gated isolated POC. Full migration remains unapproved.
Synerise is the provisional primary source; REES46 remains independently preserved.

Recommend **direct PyArrow batches → ClickHouse ArrowStream**, with immutable
six-table releases, per-file attempt restart and reconciliation before publication.
DuckDB is independent research evidence, never an ingestion bridge. This is a
provisional recommendation based on control, recovery and current mount constraints,
**not a demonstrated throughput advantage**. Native Parquet remains a benchmark
candidate. No production ingestion runner, dbt models or infrastructure changes
were implemented in this phase.

## Evidence and benchmark status

Reviewed the existing Synerise assessments, verified schema/manifests, Compose,
ClickHouse configuration, dbt sources/profiles and REES46 transport, publication,
checksum and permission code. Sources remain the six Parquet files under
`data/external/synerise/source`, archive SHA-256
`e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7`.
Expected event rows: 225,224,262; product properties: 1,534,050. These are the
hash-pinned archive counts, not the smaller published competition reference.

Docker was initially unavailable. After the user started it, read-only inspection
confirmed ClickHouse **25.8.33.6**, no active merges/other queries at the initial
check and 378,678,267,904 free bytes on the ClickHouse default disk. Existing users
and grants were inspected without changes. No service was started by this task.

The first isolated DDL attempt exposed a 25.8 compatibility issue: CHECK constraints
could not refer to an ALIAS column. The proposed constraint now references the
stored tuple directly. Its UUID/comment-owned database was cleaned up. Subsequent
attempts, including the user's requested final retry, failed the pre-DDL memory
gate. The final sample was 2,075,992,064 bytes used of 2,147,483,648, about **68 MiB
headroom**, versus the required 256 MiB. The safety gate was not relaxed.

| Measurement | Native Parquet | PyArrow → ArrowStream |
| --- | --- | --- |
| Successful source rows inserted | 0 | 0 |
| Throughput / elapsed insert time | unmeasured | unmeasured |
| Query peak memory | unmeasured | unmeasured |
| Compressed destination storage | unmeasured | unmeasured |
| Source/destination equivalence | not executed | not executed |

No performance comparison or successful end-to-end schema validation is claimed.
See [benchmark protocol](../../analysis/synerise/architecture/benchmark-plan.md),
[status](../../analysis/synerise/architecture/benchmark-status.json), initial failure
manifest and runtime snapshot. MemoryResident is process RSS; cgroup memory also
includes other accounted memory such as cache. These are samples, not ingestion
peaks. Do not substitute RSS for cgroup headroom or force eviction/restarts to pass.

## Ingestion alternatives

| Aspect | Native Parquet | Python/PyArrow streaming |
| --- | --- | --- |
| Input | seekable server file() preferred; bounded HTTP Parquet equivalent for POC | local ParquetFile.iter_batches → ArrowStream HTTP |
| Current availability | source directory is not mounted into ClickHouse | needs isolated PyArrow dependency; no service mount change |
| Memory | efficient native reader possible, but row-group buffers must be measured | explicit batch/payload control; decoder can still buffer column chunks |
| Throughput | unknown; avoids Python re-encoding | unknown; adds Arrow serialization and HTTP work |
| Recovery | file-attempt restart is simple; internal offsets not durable checkpoints | explicit source/row-group/batch diagnostics; uncertain append still needs file restart |
| Source preservation | approved read-only bind mount; no source rewriting | opens source read-only; no pandas or whole-file materialization |
| Complexity | fewer client components; mount/reader/version concerns | more client validation/metrics, clearer per-batch audit |
| Auditability | query IDs and file hashes; row-grain equivalence needed | explicit typed batch validation and request/query IDs |

Native `file()` is constrained to the server's user_files area, not arbitrary host
paths. The existing Compose has no source mount. A future read-only mount requires
approval; do not copy the whole page file into the server volume as a hidden
workaround. HTTP `INSERT FORMAT Parquet` is supported, but bounded sample behavior
cannot establish that sending a full 2 GB file fits memory.
[ClickHouse file()](https://clickhouse.com/docs/reference/functions/table-functions/file),
[Parquet format](https://clickhouse.com/docs/reference/formats/Parquet/Parquet).

PyArrow supports selecting row groups and bounded output batches. Batch output size
is not a decoder RSS guarantee; Parquet column chunks can be much larger.
[ParquetFile.iter_batches](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html).
Reuse the existing authenticated HTTP request/error handling without blind write
retries. Add explicit ArrowStream payload support rather than reuse the
REES46-specific JSONEachRow insert helper or its DuckDB source logic unchanged.

## Source-preserving schemas

[Proposed DDL](../../analysis/synerise/architecture/proposed-ddl.sql) is entirely
commented, with release/attempt placeholders. The same renderer supports only the
isolated POC. It has not passed full server DDL/data tests after the constraint fix.

| Raw table | Original fields retained |
| --- | --- |
| page_visit | client_id Int64, timestamp String, url Int64 |
| search_query | client_id Int64, timestamp String, query String |
| add_to_cart | client_id Int64, timestamp String, sku Int64 |
| remove_from_cart | client_id Int64, timestamp String, sku Int64 |
| product_buy | client_id Int64, timestamp String, sku Int64 |
| product_properties | sku Int64, category Int64, price Int64, name String |

Preserve signed source identifiers including the observed page client 0; do not
coerce through float, invent event/order/session keys or decode URL into SKU.
Query/name vector strings retain their exact whitespace and codes. Price remains
an Int64 **bucket**, not Decimal revenue. Ordinary MergeTree retains duplicates;
no ReplacingMergeTree, primary-key uniqueness assumption or DISTINCT ingestion.

All original fields are non-nullable for this specific pinned release because
all observed source null counts are zero. Input preflight/batch validation must
reject unexpected nulls, never default them to zero/empty. A source version with
nulls needs an explicitly revised schema before loading. Parquet's nullable schema
is not proof of actual missingness. Choosing Nullable instead would add roughly
one byte per nullable field per row before compression (about 0.68 GB for three
fields over all events), plus null-aware expressions and sorting policy. This is a
storage/contract choice, not permission to lose nulls in another release.

Each table also records source filename, file SHA, archive SHA, release UUID and
file-attempt UUID. These are transport provenance, not unique business-event IDs.
Defaults are controller-supplied constants; acceptance checks verify their values.
Retain an external manifest with source/footer/schema and software versions.

## Source-clock representation

ClickHouse DateTime/DateTime64 do not provide a truly timezone-naive civil timestamp:
omitting the timezone uses server context; the inspected server reports UTC. Do
not use that as evidence the source is UTC, or silently localize its strings.
[DateTime semantics](https://clickhouse.com/docs/reference/data-types/datetime).

The proposed parsed analytical timestamp is therefore a named
`Tuple(day Date32, second_of_day UInt32)` called `event_time_source`, derived only
from the original date/hour/minute/second components. This explicitly represents a
civil timestamp without a timezone. `source_day` is an alias; `source_second` is
an alias for calendar days since 1970-01-01 × 86400 plus second-of-day. That number
is **a source-clock ordinal, not Unix epoch time**. Shape/HMS/date round-trip checks
reject malformed clocks. No UTC conversion, Z suffix or hidden offset is applied.
[Named tuples](https://clickhouse.com/docs/reference/data-types/tuple).

Numeric cutoff comparisons use this ordinal; calendar filters use source_day.
A 14-day label is `[t,t+1,209,600 source-clock seconds)`, and history is strictly
less than t. These are not verified physical elapsed hours across unknown DST.
Same-time records cannot establish order, especially with the measured five-second
clustering. Future timezone clarification creates a new clock-policy/derived release
and explicit label reconciliation, never silent reinterpretation of old runs.

Metabase must expose source date/hour and formatted civil text instead of pretend
UTC datetimes; Python may parse the preserved string into a naive timestamp.
This integration is a POC acceptance gate: tuple handling and dbt macros require
validation on the installed versions. It is a deliberate representation compromise
because ClickHouse lacks the requested native naive timestamp type.

## MergeTree layout and access patterns

Event tables: monthly source-day partitioning (seven observed calendar-month
partitions, including partial June/December). Sorting: client_id, source_second,
then SKU or URL where present. Search sorts by client/time without its large query
string in the key. Properties are unpartitioned and sorted by SKU. Sorting is
clustering, not deduplication or order identity.

Start with index_granularity 8192, ZSTD(1) on original columns and default compression
on derived/provenance columns. No speculative bloom filters, projections or extra
skip indexes until query evidence justifies them. Monthly pruning supports bounded
feature/funnel scans; client-first order supports histories and ASOF sequences.
Include explicit source_day bounds as well as ordinal cutoffs so partition pruning
does not depend on optimizer inference. Global daily dashboards should read small
daily marts rather than repeatedly scan 199M pages. Measure alternative key/codec
choices in the later benchmark; none is a measured winner yet.

## Physical budgets

Configured limits remain **2 GiB container / 1.5 GiB server / 2 CPUs**. Existing
client queries use two threads, 512 MiB query cap and external grouping/sorting at
128 MiB. Background pools are 16 main/16 scheduled, two move/fetch/common; these
limits do not reserve free memory for ingestion. Current grants and configuration
are preserved. Host free disk (~1.4 TiB) is not the same as container-volume free
space; live ClickHouse disk showed about 353 GiB free.

Proposed initial ingestion: one writer, one request in flight, one insert thread,
10k rows and <=8 MiB serialized batch; 50k only after measured headroom. Begin with
a 64 MiB POC query cap, then evaluate at most 256 MiB per ingestion/reconciliation
query when cgroup/server margins permit. Cap Python separately (planning target
768 MiB RSS), use_threads=False and monitor Arrow buffers plus process RSS. No
pandas, prefetch queues or simultaneous dbt/BI heavy scans during approved loading.
Do not raise global limits or stop services automatically to obtain headroom.

Archive + extracted Parquet is 4.35 GiB. Compressed ClickHouse raw size is unknown;
reserve **10–20 GB per complete release as a planning allowance**, not a forecast.
A retained prior release, full candidate and one failed large-file attempt can
require up to three such allowances; reserve another 20–40 GB for merge/temp work
and up to 80 GB on the independent validation scratch filesystem. Check both filesystems
before starting, and enforce a stop threshold rather than consume the last space.
These conservative reservations must be revised after bounded sample measurements.

Background merges rewrite parts and temporarily consume disk/RAM. Small batches
spread across months can create many parts. One writer, natural backpressure and
part-count/merge monitoring are preferable to globally disabling merges or running
OPTIMIZE FINAL. Monitor system.parts, system.merges, system.processes, query_log,
system.disks and RSS/cgroup samples. Pause new work on a margin breach; leave
published REES46 and completed Synerise releases untouched. Full runtime/throughput
remain unmeasured; do not extrapolate the earlier REES46 JSON/DuckDB transfer as a
validated Parquet load benchmark.

## Idempotency, interruption and recovery

Use archive/file SHA + schema version + clock-policy version as dataset identity;
UUIDs identify each release and file attempt. Verify all source hashes before and
after each file, and footer/schema/null policy before insertion. Use a local
advisory lock and durable manifests (write temp, fsync, atomic replace). Multi-host
or out-of-band writers are outside this design's supported scope.

Acknowledge batches synchronously. Checkpoint acknowledged progress for diagnostics,
not permission to resume an uncertain append. On a timeout, memory error, partial
acceptance, termination or lost response, abandon that **file's** table; wait for
its query to end and start a new UUID file attempt from the beginning. Do not retry
uncertain INSERTs, use business deduplication keys or trust block deduplication to
provide exactly-once semantics. Other fully validated files may be retained.
The dominant page file can require a complete retry; simplicity costs restart time.
Per-batch staged-part publication could reduce that cost but adds substantial
recovery complexity and many objects; defer it until measured need.

Only a fully reconciled file can be renamed into its private release's final table
name. Lost RENAME acknowledgements are resolved by table UUIDs; never repeat a swap
blindly. On restart, manifests are reconciled with actual UUIDs/query status rather
than assuming client acknowledgements describe server state. Corrupt stages,
changed sources, duplicate-run attempts and concurrent controllers cannot publish.
Ownership-scoped cleanup requires exact UUID/comment validation; never wildcard DROP.

## Dataset-wide publication and rollback

Six independent table RENAME/EXCHANGE operations are not a dataset-wide transaction.
Build all six under immutable `synerise_raw__<release>` databases. Grant consumers
no access while the candidate is incomplete. After complete reconciliation,
quiesce/revoke the writer, grant exact read-only access, and atomically replace one
local release-manifest pointer. Consumers resolve/pin its database UUID/name once
per run. Crash before replacement selects the previous release; after replacement
selects the complete candidate. Resolve pointer state after an uncertain response.

Rollback selects the retained previous release pointer, never modifies REES46.
Changing Metabase connections or BI mart deployments is a separate approved step;
a raw pointer alone cannot switch several dashboards atomically. No database-wide
rename/swap or mutable multi-source routing is assumed. See
[workflow and state transitions](../../analysis/synerise/architecture/workflow.md).

## Source-to-destination reconciliation

Validate actual Parquet, not only the old DuckDB aggregates. PyArrow streams footer,
schema, nulls, raw strings and signed IDs directly. For each file compare exact
rows, min/max original/parsed times, per-column null/empty counts, mapping/provenance,
exact clients/SKUs and duplicate multiplicity histogram, plus canonical checksums.
Properties must retain all 1,534,050 unique SKU keys and cross-source joins must
have zero unmatched SKU rows for this release. No row-count-only success.

Canonicalize fixed-order original fields using UTF-8 byte lengths and decimal signed
integer strings; add a source-type tag. Empty versus null must remain distinct
(if a future nullable schema is approved). Reuse the REES46 framing/hash principles,
not its hard-coded columns or UTC timestamp encoder. Independently compute two
MD5-half UInt128 sums, 64-bit XOR and row counts, by file/month/client bucket. Exact
duplicates affect sums; a checksum is probabilistic evidence, supplemented by exact
aggregate/multiplicity checks. Validate the parsed tuple independently from raw
text; verify provenance separately from original payload. Do not hash only values
generated from expected constants while ignoring actual stored data.

Avoid grouping 199M page rows at once. Use deterministic positiveModulo(client_id,64)
buckets, further bounded by source month for duplicate grouping; properties bucket
by SKU. Source Python uses the identical signed-positive modulo rule. Clients lie
in disjoint buckets, so global exact-client totals sum bucket totals, not monthly
unique counts. Timestamp-containing duplicate groups cannot cross months.

An independent source validator can use bounded canonical-key sort runs on scratch
disk and fan-in-limited external merge: count identical keys and contiguous client/SKU
prefixes without holding the whole dataset in a Python set. This validator is a
future implementation requirement, not implemented performance evidence here.
Bound buffers by measured RSS, not raw bytes alone. DuckDB research outputs provide
additional regression expectations, but do not participate in ingestion or replace
fresh Parquet validation. [Example reconciliation SQL](../../analysis/synerise/architecture/reconciliation.sql).

## Proposed dbt analytical layers

Design only; existing dbt project/models remain unchanged.

- Raw sources: six explicitly release-pinned tables in the immutable raw database.
- Staging views: preserve original columns and provenance; UNION ALL five event
  types into typed client/time/type/SKU-or-NULL/URL-or-NULL/query-or-NULL rows. No
  UNNEST, cross join to vectors or event multiplication. Parse optional vector
  arrays separately while retaining original strings.
- Intermediate: customer daily histories, bounded strict page/cart/buy funnels,
  optional-search branch, same-client/SKU cart→buy, A event/B timestamp occasion/C
  purchase-day sensitivity views. No invented sessions, orders or product views.
- Marts: daily engagement/funnel aggregates and customer snapshot features/labels,
  with source release, schema and clock-policy identity in every output key/manifest.

For historical snapshots, filter raw ordinals strictly before cutoff before session-
like or frequency summaries; use only the half-open future interval for labels.
Do not import whole-period customer attributes into features. Static product category/
price-bucket availability needs its documented historical assumption. Missing activity
gets zero counts; ratios handle zero denominators. Reconcile initial August–November
cohorts against measured research labels before claiming parity.

Start with views and bounded partition-at-a-time tables, not one full-history model
that repeatedly sorts pages. Incremental daily aggregates may be needed for workload,
but correctness comes first: use explicit release/day replacement and rebuild affected
partitions, never append the same static archive on rerun. Snapshot marts are keyed
by release/policy/cutoff/client, built one cutoff at a time. Historical input is static;
there is no justified live watermark/Kafka/late-event service in this phase.

## Least-privilege access

Current provisioning grants ingestion management on ecommerce.*, dbt read on
`ecommerce.raw_events` plus transformation writes in ecommerce_analytics.*, BI raw
read, and retains legacy ecommerce_app. They are not suitable Synerise grants by
default. Existing ML Compose currently reuses the general app credential; do not
carry that broad access into the future feature extractor. No users/credentials
were changed here. Runtime grants are saved in the research snapshot.

Propose new dedicated identities, scoped to exact release/schema names:

| Identity | Proposed rights |
| --- | --- |
| provisioning controller | create candidate databases/assign grants; not a routine loader credential |
| synerise ingest | SELECT/INSERT and table lifecycle only in its private candidate database |
| synerise dbt | SELECT on one approved raw release; transformation DDL/DML only in its analytics release |
| synerise BI | SELECT on approved marts and necessary metadata; no raw writes |
| synerise ML | SELECT on approved feature/label marts only; no raw, DDL or writes |

Publication/grant control is separate from app execution. Revoke candidate writer
access after validation/quiescence; published releases are read-only. Use explicit
database allowlists, not grants on ecommerce.* or global privileges. Provisioning
and role-denial tests require a later approval; no existing Metabase connection is
switched. Synerise and REES46 stay distinct in database names, source tags and lineage.

## Implementation sequence and decision gates

1. Review civil-time representation, non-null contract, names, source/version/license
   limits, resource gates and immutable-release publication. No full-load approval implied.
2. Finish safe POC: corrected DDL, 10k samples both methods, all six types plus
   Unicode/null-rejection/duplicate/tie/boundary fixtures. No resource-gate bypass.
3. Repeat comparable warm/cold-order trials and cautiously scale bounded samples.
   Verify reader RSS, client RSS, query peak, storage, failure/recovery and cleanup.
4. Implement/test the direct source validator, manifests, file-attempt recovery,
   role denials, pointer crash recovery and stale-writer protection.
5. Seek explicit full-migration approval. Load smaller sources first, pages last,
   validating each and the complete release; do not publish partial data.
6. After raw acceptance, separately approve dbt, feature reconciliation, BI and ML
   extraction phases. No model training, Kafka or dashboard implementation here.

Risks remain: unknown source timezone/DST and release-count explanation, source
tracking/identity completeness, absent order/session/page-type mapping, undated
properties, NonCommercial restrictions, decoder allocation and page retry cost,
small-sample benchmark bias, client sort overhead, external validation runtime,
container cache/headroom fluctuations and cross-consumer release pinning.

**CONDITIONAL GO** for these bounded implementation steps, with the first successful
POC and review required before full loading. Preferred Python streaming is justified
by bounded controller/recovery visibility and no service-mount prerequisite; sustained
performance remains undecided until a safe measured comparison passes.

## Preservation and validation

Before/after hashes cover protected local source, DuckDB, configuration, credentials,
dbt and migration files (private credential hashes are not exported). The inspected
REES46 table UUID remains `9242f083-29f7-465e-a9ee-165c03a53f47`, with 20,692,840 rows.
Only the UUID-owned POC database was created/dropped; no POC database remained at
verification. No full data inserts, source changes, service-limit changes, existing
table exchanges, production models, credential changes, commits or pushes occurred.

Design artifacts, schema renderer, guarded POC, status and workflow live under
[analysis/synerise/architecture](../../analysis/synerise/architecture/README.md).
Proposed production DDL/reconciliation queries remain unexecuted. Live benchmark
limitations are explicit rather than invented metrics; local design/temporal checks
and protected-file comparison are recorded in the handoff artifacts. All 37
protected-file hashes match; four local design/temporal tests and Ruff passed.
