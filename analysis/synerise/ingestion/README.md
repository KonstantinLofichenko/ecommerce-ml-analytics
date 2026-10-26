# Current result — permanent bulk load complete

`synerise_raw` now contains all six tables: **226,758,312 rows**. See the
[bulk-load report](../../../docs/reports/phase-3.5-synerise-bulk-load.md),
`bulk.py`, `bulk-results.json` and `bulk-executed.sql`.
The count-only native import succeeded in 31.489 seconds. The existing private
release was not reused or removed. `bulk.py --execute` refuses an existing populated
destination; do not replay its INSERT audit. No checksums or duplicate scans ran.

The following section describes the earlier, separately retained private attempt.
Its custom memory gates and detailed acceptance policy do not apply to `bulk.py`.

# Phase 3.5 continuation — native load with streaming acceptance

**Partial, private, stopped at the cgroup safety threshold.**
[Report](../../../docs/reports/phase-3.5-synerise-native-ingestion.md).
Database: `synerise_raw__8efbe3d95dfc431cb1fa66f980f13a67`.
Four validated tables retain 14,082,563 rows; search staging was retired and page
was not attempted. BI/dbt access probes were denied. No publication pointer exists.

The previous 21 October global-tracker failure is archived under
`history/2026-10-21-failed/`. Its exact duplicate-histogram policy is superseded by
the user's continuation instructions; this run executed no record-level grouping.
No Compose/service/resource configuration changed during this continuation.

## Implementation and evidence

- `native.py`: existing one-controller SQL orchestrator and shared architecture DDL.
  Original Parquet → native `file()` → INSERT SELECT. Python transports only SQL,
  aggregate results and manifests. One writer, one thread, no insert retries.
- `results.json`, `*-validation.json`: current release and per-file state, UUIDs,
  original-file hashes, source/destination checks, query IDs, resources and cleanup.
- `executed.sql`: exact SQL audit for this release, **not an idempotent replay script**.
- `reconciliation.csv`, `performance.csv`: generated numeric comparisons/metrics;
  `counts.md`, `performance.md` are corresponding report tables.
- `validate_encoding.py`, `encoding-validation.json`: independent hashlib/byte
  reference versus synthetic SQL, including null, UTF-8, signed IDs and duplicates.
- `preflight.py`: idle/resource preservation baseline; credential hashes stay in
  private `/tmp/synerise-native-preservation.json`, not public artifacts.
- `finalize.py`: verifies retained table identities/counts and protected resources,
  waits for natural query-log flushing, reports incomplete publication and may remove
  only a UUID/comment-owned **empty failed** database. It retains validated data.
- `report.py`: regenerates aggregate CSV/Markdown tables from actual results.
- `test_native.py`: acceptance, source-path, byte-encoding and partition-combination
  checks. Existing architecture/recovery tests remain applicable.

## Checksum policy

`synerise-row-v2` prefixes source and ordered column names/types, then appends `N`
for null or `V<byte_length>:<UTF-8 value>` for each original column. Integers use
signed decimal values. Independent MD5-128 and SHA256-prefix-128 values (interpreted
little-endian) are summed into UInt256; SHA256-tail-64 also contributes XOR.
Separate queries scan original Parquet and stored columns. These hashes are not
file-byte SHA-256. The independent fixture validates SQL encoding against hashlib.

Properties use one streaming aggregation; events use seven disjoint source months
(June–December 2022) after whole-source bounds checks. Partition sums/counts add,
XORs XOR, extrema combine with min/max excluding empty partitions. Counts must sum
to the expected full file. No full-source original-row GROUP BY, duplicate histogram,
or distinct-SKU aggregation remains in the normal acceptance path. Multiset checks
are strong probabilistic evidence, not formal proof of identical rows.

Native 10k reader blocks and 100k-row/16 MiB insert-squashing targets remain; one
512 MiB query cap with 64 MiB external thresholds. The unchanged monitor checks
RSS, cgroup total, server tracker, disk, merges and active parts. Operation records
include tracker/resource snapshots before and after. Cgroup stop is >6.5 GiB,
tracked-memory stop >5 GiB, disk floor 40 GiB. Short spikes can beat polling.
No restart, cache purge, limit increase or threshold change was used.

This run stopped because cgroup total reached 6.58 GiB, despite low tracked memory.
Post-stop memory.stat showed ~4 GB file cache. This is evidence to review the gate,
not permission to bypass it. No further INSERT occurred after the stop.

## Commands and recovery limits

Do not automatically rerun ingestion while the cgroup policy is unresolved.
The runner's entry point starts a **new** release; it does not automatically attach
to this retained partial release. A reviewed continuation must explicitly reuse
and reverify the four validated table UUIDs and start fresh search/page attempts.
Never replay `executed.sql` or append to an uncertain/failed attempt.

Commands used for this attempt, from repo root:

```bash
source .venv/bin/activate
PYTHONPATH=src python analysis/synerise/ingestion/preflight.py
PYTHONPATH=src python analysis/synerise/ingestion/validate_encoding.py
PYTHONPATH=src python analysis/synerise/ingestion/native.py --execute-native-load
```

After success or failure, run finalization separately (not with `&&` after a failed
loader); keep the matching private baseline and archive results before another run:

```bash
PYTHONPATH=src python analysis/synerise/ingestion/finalize.py
PYTHONPATH=src python analysis/synerise/ingestion/report.py
pytest -q analysis/synerise/ingestion/test_native.py \
  analysis/synerise/architecture/test_design.py \
  analysis/synerise/architecture/benchmark/test_guards.py
ruff check analysis/synerise/ingestion analysis/synerise/architecture
ruff format --check analysis/synerise/ingestion analysis/synerise/architecture
docker compose config --quiet
```

A complete, validated private release is an allowed final state, but this database
is **incomplete**. Existing credentials/grants, raw REES46 tables, immutable Synerise
files, volumes, dbt, Metabase and AIS are preserved. No ML or infrastructure phase
begins here. No dependencies were added.
