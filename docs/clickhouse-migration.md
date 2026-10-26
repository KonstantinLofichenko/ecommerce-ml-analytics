# Historical raw migration — Phase 3.2

The validated DuckDB file is immutable reference input. This phase publishes only
`ecommerce.raw_events`; it does not rebuild sessions, customers, features,
dashboards, DAGs or models. AIS infrastructure is never used. The existing 2 GB
ClickHouse container and 1.5 GB server memory budget remain unchanged.

## Source and destination contract

DuckDB has eleven nullable columns: original CSV attributes as VARCHAR, source
`month` as VARCHAR, and `event_time_utc` as UTC-normalized TIMESTAMP. Source IDs
are strings, not numeric keys or globally unique session identifiers. Required
schema, valid YYYY-MM provenance, parseable timestamps/consistent UTC
normalization and exact price representability are checked before any load.
Unknown/unsupported values cause an explicit error, never dropped rows or silent
rounding. Valid input nulls remain nulls.

| Column | ClickHouse type | Meaning |
| --- | --- | --- |
| event_time | Nullable(String) | Original timestamp text, unchanged |
| event_type | LowCardinality(Nullable(String)) | Original event type |
| product_id / category_id | Nullable(String) | Original identifiers, preserving leading zeros |
| category_code / brand | LowCardinality(Nullable(String)) | Original sparse category/brand values |
| price | Nullable(Decimal(18,2)) | Exact typed monetary value; negative values retained |
| price_raw | Nullable(String) | Original price text, including its formatting |
| user_id / user_session | Nullable(String) | Original customer/session identifiers |
| month | String | Nonmissing source-file YYYY-MM provenance |
| event_time_utc | Nullable(DateTime64(6,'UTC')) | Original normalized timestamp, preserving microseconds |

The initial data has prices from -79.37 to 327.78, all exactly representable with
two decimal places. `price_raw` ensures the typed addition cannot erase original
formatting. Timestamps are explicitly UTC; original event text is preserved too.
No original attribute is omitted. The twelve destination columns comprise the
eleven source columns with price typed plus the added original-price string.

Use ordinary **MergeTree**, partitioned by source `month` (five partitions).
`ORDER BY (month, ifNull(user_id,''), ifNull(user_session,''),
ifNull(event_time_utc,toDateTime64(0,6,'UTC')), ifNull(product_id,''))` clusters
customer/session history within months and supports future time-window analytics.
`month` is provenance, not a timezone-dependent calculation. Null sentinels are
used only in the sorting expression; actual nulls remain intact. Sorting is not
a uniqueness constraint. ReplacingMergeTree, UNIQUE constraints and event
filtering/deduplication are not used. `insert_deduplicate=0` preserves even
identical rows/blocks deliberately present in the source.

## Credentials and least privilege

Bootstrap using the existing local administrator; existing passwords are never
rotated and `ecommerce_app` remains unchanged to preserve saved Metabase
connections:

```bash
source .venv/bin/activate
python scripts/bootstrap_clickhouse.py --generate-missing
```

`--generate-missing` appends missing restricted-account variables to private
`.env` (or fills empty role placeholders), never changes existing populated
values. The normal generator also includes these fields for new checkouts.
`.env.example` contains usernames and empty password placeholders only.

| Account variables | Scope |
| --- | --- |
| CLICKHOUSE_USER / PASSWORD | Existing administrator; provisioning only |
| CLICKHOUSE_INGEST_USER / PASSWORD | Read, insert and table lifecycle in ecommerce for staging/publication |
| CLICKHOUSE_DBT_USER / PASSWORD | SELECT ecommerce.raw_events; create/transform objects only in ecommerce_analytics |
| CLICKHOUSE_BI_USER / PASSWORD | SELECT ecommerce.raw_events only |

`CREATE USER IF NOT EXISTS` does not rotate existing credentials. Changing .env
passwords alone is not a password-change procedure. Coordinate an explicit ALTER
USER and application update for future rotations. The dbt Compose service now
uses the restricted dbt credentials and target schema `ecommerce_analytics`;
its raw source declaration still resolves `ecommerce.raw_events`. Metabase is
not automatically changed: optionally edit the saved connection to use the new
BI user/password after verifying it. Do not enter the ingestion/admin password
into a read-only BI connection. Run permission probes with:

```bash
python scripts/check_clickhouse_permissions.py
```

Those probes read counts, attempt zero-row raw INSERTs (only ingestion may do so),
and create/drop a UUID-named view only in the transformation schema. No real
production rows are appended. No credentials are logged or included in URLs.

## Run and monitor

```bash
docker compose up -d --wait clickhouse
python scripts/migrate_clickhouse.py --batch-size 50000 --attempts 2 \
  > data/processed/migration-progress.jsonl 2>&1
```

The source defaults to `data/processed/ecommerce.duckdb`; expected source count
is 20,692,840. Options: `--source`, `--output`, `--batch-size` (1–250,000),
`--attempts` (1–5), `--expected-rows`, `--url`, `--validate-only`, `--force-reload`.
The host URL defaults to http://127.0.0.1:$CLICKHOUSE_HTTP_PORT and can be supplied
through `CLICKHOUSE_MIGRATION_URL` or `--url`. Shell exports override literal .env
values. Prefer the generator's URL-safe secrets; the small reader handles literal
quoted/unquoted values, not full shell interpolation. Inside a container, use
http://clickhouse:8123 and pass the appropriate restricted credentials explicitly.
Rebuild the ML image to include the new scripts first; its data mount is read-only,
so use an output path such as `--output /tmp/migration-artifacts` inside that
container. The documented host command is the primary validated execution path.

DuckDB opens read-only inside a read transaction. Sequential `fetchmany` batches
contain JSON strings serialized by DuckDB itself, not a full Pandas dataset or
floating-point monetary conversion. Python joins/UTF-8 encodes at most one batch
and sends gzip-compressed JSONEachRow over authenticated HTTP. No concurrent
inserts, broker, external loader or extra Python dependency is introduced.

DuckDB has a 2 GB working-memory limit and temporary spill space. ClickHouse
queries use two threads, a 512 MiB per-query limit and 128 MiB external
aggregation/sort thresholds, below its unchanged development container budget.
The initial batch size is 50,000 rows (414 batches). Lower it if host/server
pressure persists. Allow extra disk for source-query spill, staging, merge
workspace and retained backups; a failed stage is intentionally not auto-dropped.

```bash
tail -f data/processed/migration-progress.jsonl
docker stats --no-stream ecommerce-ml-clickhouse-1
docker compose logs --tail 100 clickhouse
```

JSON progress events report attempts, batch number, acknowledged rows, total,
throughput and reconciliation partitions. Acknowledged rows are not necessarily
committed rows after a lost response. State files under `data/processed/phase-3.2/`
track stage identity/status. `reference.json`, `differences.json` and `result.json`
record complete aggregate comparisons and outcome. `initial_result.json` retains
the first successful publication, and before/after source-file SHA-256 checks are
recorded automatically by completed runs. This directory is ignored by
Git. Preserve result.json separately when retaining the initial run's timings;
a later validation/no-op run replaces result.json with that run's result;
initial_result.json remains the first publication. Render the phase report from
these artifacts using `python scripts/report_clickhouse_migration.py`.

## Idempotency, publication and recovery

Every attempt uses a new `_raw_events_stage_<uuid>` table. Reads retry transient
transport errors with bounded exponential backoff. Writes are never blindly
retried: a transport/server-500 failure during insertion or stage validation
abandons that attempt and starts a new stage from source row zero. This avoids
assuming an INSERT failed merely because its HTTP acknowledgement was lost.
Partial stages cannot feed the published table. Permanent source/schema/SQL or
reconciliation errors stop immediately.

An existing managed destination is reconciled before loading. If identical,
the normal command succeeds as `validated_noop` with **zero inserted rows**.
`--force-reload` deliberately builds a fresh complete stage. Unmanaged or
schema-incompatible destinations are refused, not overwritten.

Only a fully reconciled stage is published, in an Atomic database:

- First load: a single RENAME TABLE stage TO raw_events.
- Replacement: EXCHANGE TABLES raw_events AND stage. The stage then holds the
  previous destination as an explicit rollback copy; it is retained.

The destination UUID is checked before publication. An uncertain RENAME/EXCHANGE
response is resolved by checking the resulting destination UUID. The exchange is
never retried, since a second exchange would undo a successful first one. This
is tested with a simulated committed exchange/lost acknowledgement.

Use one operator and the same output directory for a target. A local advisory
lock blocks competing processes using that directory; it is not a distributed
lock and separate output paths/hosts must not be used concurrently. Out-of-band
writes to the raw table are unsupported. Restricted dbt/BI credentials cannot
write raw rows, reducing this risk.

### Interrupted before publication

Check the stage state/progress log and published table UUIDs. Re-run the normal
migration: it validates a complete destination or starts a fresh independent
stage. Do **not** append/resume into a partially acknowledged stage. Existing
published data is unchanged. Inspect with authenticated SQL in ClickHouse /play:

```sql
SELECT name, uuid, comment FROM system.tables
WHERE database='ecommerce' AND (name='raw_events' OR startsWith(name,'_raw_events_stage_'));
SELECT table, sum(rows), sum(bytes_on_disk) FROM system.parts
WHERE database='ecommerce' AND active GROUP BY table;
```

After confirming a manifest marks a stage abandoned/failed and its UUID is not
the current published table, an operator may explicitly drop **that exact stage**:

```sql
-- Replace the UUID suffix with the inspected abandoned stage name only.
DROP TABLE ecommerce._raw_events_stage_REPLACE_WITH_INSPECTED_UUID;
```

Never drop the published raw table, all stage tables by wildcard, or Docker
volumes. Retain old validated generations if rollback may be needed.

### Interrupted during publication or explicit rollback

Compare actual UUIDs with the stage state and expected previously published UUID;
do not repeat an exchange based on a missing log line alone. Newer state records
include staging/published UUIDs and a `publishing` intent; older initial-run
records can be resolved through system.tables and the logged stage name.
For an intentional rollback of a replacement, first confirm that the retained
stage is the **previous validated destination**, not an incomplete failed stage:

```sql
-- Explicit operator action only, never an automatic retry.
EXCHANGE TABLES ecommerce.raw_events AND ecommerce._raw_events_stage_REPLACE_WITH_VALIDATED_BACKUP_UUID;
```

Then re-run `--validate-only`. If rolling back to an older source version,
reconcile against that version, not a changed current source. An initial load has
no previous destination to roll back to; a healthy first publication should not
be exchanged with an abandoned partial stage.

## Reconciliation strength and limits

For each source month, compare row counts, event-type counts, UTC min/max,
distinct users, every nullable column and **exact integer minor-unit price sums**.
Global distinct users are computed separately rather than summed across months.
No money tolerance is needed: typed values are exact and differences must be zero.
Money sums cover all raw events; they are not revenue/order totals.

Duplicate distributions group all nine original attributes, including nulls,
then compare the number of groups at every multiplicity within each partition.
Source provenance is not used as an artificial event identifier. No groups are
removed. The initial source has no event-time/source-month mismatches, so original
identical timestamped rows cannot span different source-month partitions.

A canonical row representation length-prefixes each UTF-8 value. `-1:` means
NULL, `0:` means empty, and delimiters/newlines/Unicode cannot collide. It includes
all original strings plus provenance, the UTC timestamp formatted to six decimal
places and integer minor-unit typed price. Each engine independently computes
MD5 over its actual stored columns. Per partition, two UInt64 digest-half sums
(accumulated as 128-bit integers), a UInt64 XOR and row count form order-independent
multiset checksums. Sums retain duplicate multiplicity; XOR alone would not.
The same representation and endian normalization are tested on synthetic Unicode,
NULL, empty-string, negative-price and microsecond rows. Digest checks are strong
probabilistic evidence, not a mathematical proof against adversarial MD5 collisions.
They complement exact counts/multiplicity distributions rather than replace them.

```bash
python scripts/migrate_clickhouse.py --validate-only
ECOMMERCE_CLICKHOUSE_TESTS=1 pytest tests/test_clickhouse_migration.py
pytest
ruff check .
ruff format --check .
docker compose --profile tools run --rm dbt debug
docker compose --profile tools run --rm dbt test
```

Live tests use UUID-scoped temporary ClickHouse databases, then drop only those
owned test databases. Without ECOMMERCE_CLICKHOUSE_TESTS=1, live tests explicitly
skip; offline source checks still run. No production source/ML feature tests are
replaced. dbt declares a raw source with observed non-null/event/month constraints
and a fixed historical count test; it creates no session/funnel/customer models.

See [measured migration report](reports/phase-3.2-migration.md) for timings,
resource samples, checksums, duplicate statistics, tests and outstanding cleanup.

Primary reference: [ClickHouse EXCHANGE](https://clickhouse.com/docs/sql-reference/statements/exchange).
The isolated restart strategy deliberately avoids dependence on bounded
[insert deduplication windows](https://clickhouse.com/docs/guides/developer/deduplicating-inserts-on-retries).
