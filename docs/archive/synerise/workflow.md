> Historical archive: this document records an earlier investigation or proposal.
> It does not describe current deployment state. See the [current funnel contract](../../funnel-data-contract.md).

Supporting scripts and fixtures retain their original paths in
`analysis/synerise/architecture/`; relative code filenames in this historical
proposal refer to that directory, not this archive.

# Proposed workflow — not a full-migration entry point

No commands here start services, change mounts, grant users or publish data.
Production runner is deliberately not implemented in this phase. `schema.py` and
`benchmark.py` support only the isolated POC. `proposed-ddl.sql` is entirely commented.

## Option A: native Parquet

Future approved read-only mount:

```yaml
# Proposal only; not added to compose.yaml.
# Exact source version directory, readable by ClickHouse UID, no chmod of source.
- ./data/external/synerise/source:/var/lib/clickhouse/user_files/synerise/e90b8fde:ro
```

Then server-side native loading can use a seekable file under user_files:

```sql
-- Example only, private attempt table, original columns explicit.
INSERT INTO synerise_raw__RELEASE._page_visit_ATTEMPT (client_id,timestamp,url)
SELECT client_id,timestamp,url
FROM file('synerise/e90b8fde/page_visit.parquet','Parquet',
          'client_id Int64, timestamp String, url Int64')
SETTINGS max_threads=1,max_insert_threads=1,max_memory_usage=268435456,
         input_format_parallel_parsing=0,insert_deduplicate=0;
```

Current Compose does not mount these files. `file()` cannot read arbitrary host
paths. Adding the mount requires a later approved service change; not done here.
The POC's native equivalent posts a **bounded** Parquet payload using HTTP
`INSERT ... FORMAT Parquet`, so it requires no mount. Its results do not prove a
whole-file stream or server-side file() has the same memory/throughput. Never post
the entire 2 GB page file as an untested HTTP fallback.

## Option B: PyArrow streaming, recommended provisionally

```python
# Pseudocode only; no production runner or hidden automatic retries.
verify_source_file_sha256_and_schema()
for row_group in parquet_footer.row_groups:
    for batch in ParquetFile(path).iter_batches(
        batch_size=10_000, row_groups=[row_group], use_threads=False
    ):
        validate_batch_nulls_types_clock_and_payload_budget(batch)
        send_synchronous_ArrowStream_insert_once(private_file_attempt, batch)
        record_acknowledged_progress_for_diagnostics()
validate_file_against_fresh_Parquet_counts_hashes_and_exact_external_sort()
verify_source_hash_unchanged()
resolve_single_table_rename_by_uuid()
# Repeat all six; never expose partial release.
validate_complete_release_manifest_and_cross_source_keys()
remove_writer_access_after_quiescence()
atomically_publish_local_manifest_pointer_for_new_consumers()
```

Transport: existing authenticated stdlib HTTP client with explicit ArrowStream
format, one request in flight and no insert retries. Its generic request handling
is reusable; REES46 SQL and JSONEachRow insert helper are not reused unchanged.
PyArrow is a new future ingestion dependency, not a DuckDB bridge. No full
DataFrame, row explosion, permanent deduplication or production objects.

Batch size is a starting target, not an allocation guarantee: Parquet readers can
decode a column chunk/row group behind a small iter_batches result. Measure Python
RSS/Arrow allocator and decoded bytes. Use 10k rows and <=8 MiB serialized payload
initially, max 50k only after benchmark; use_threads=False, one row group decoder.
A row group is ~1,048,576 rows, **not** a safe insertion batch by itself.

## File-attempt recovery and publication

Keep a local fsync'ed manifest keyed by archive SHA, six source SHAs, schema version,
clock policy, release UUID, file-attempt UUID and staging table UUID. Use an advisory
lock for the local controller; distributed/multi-host ingestion is unsupported.

Progress offsets are diagnostic, not proof that resuming an uncertain append is
safe. If an insert acknowledgement is lost, it partially commits or the process
terminates, mark that file attempt uncertain; wait until its query is no longer
active. Do not retry its insert. Build that file in a new UUID table from byte/row
zero. Retain already **fully validated** other files; this avoids restarting all
six files. Failed page attempts can still require reloading 199M rows; accept this
cost initially. Per-batch table/part checkpoints would add many objects and a second
publication protocol; defer until evidence justifies them. MergeTree block tokens
are not business keys and must not remove genuine duplicate source records.

After full file reconciliation, rename its private table once within the private
release database. Resolve lost rename acknowledgements from immutable UUIDs, not
another rename/swap. A fresh attempt cannot write into an already validated table.
No existing REES46 table is a destination or rollback object.

Six table RENAME/EXCHANGE operations are **not** a dataset-wide atomic transaction.
Use immutable `synerise_raw__<release>` databases. Ingestion can access only the
private attempt release. Consumers cannot access it until all six pass. Publication
is one atomic local release-manifest pointer replacement (temp file, fsync, replace,
directory fsync), with consumer/dbt commands reading and pinning it once per run.
Record the old pointer and both release UUIDs. Keep old immutable releases for
rollback, which changes the pointer, never source or REES46 data. A crash before
pointer replacement leaves the old release active; after replacement it selects a
fully verified release. Reconcile pointer state on restart rather than repeating
mutable swaps. A local pointer is a local single-controller contract, not a
multi-host distributed catalog.

BI/dbt also pin a release: do not dynamically resolve a pointer separately for each
raw source within one query/run. Metabase connections/marts are switched only in a
separate approved deployment step. Do not claim all existing dashboards switch
atomically merely because the raw release pointer did.
