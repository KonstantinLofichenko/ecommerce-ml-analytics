# Architecture

## Historical foundation: local batch exploration

```text
Manually downloaded REES46 CSV (data/raw, immutable)
    → scripts/explore.py (arguments, output, exit codes)
    → ecommerce_analytics.analytics.exploration (validation and SQL)
    → DuckDB temporary table and full-file aggregations
    → aggregate Pandas frames → terminal report
```

The reusable API accepts a local path and returns a typed report. SQL performs
counts, distinct counts, timestamp bounds, missingness, duplicate detection, and
daily grouping. Pandas handles only aggregate results and presentation. A temporary
DuckDB connection closes after each run; no persistent database or processed
artifact is created. DuckDB manages working memory and can spill intermediates
to disk. Exact distinct-row counting may be the most expensive aggregation.
Input values remain strings to preserve identifiers and duplicate semantics;
timestamps are validated and cast for temporal queries. Dates are grouped in UTC.
Synthetic tests exercise data quality and CLI failure behavior without a dataset
download. Reserved package directories contain no infrastructure implementation.

## Implemented: Phase 1.2 behavior exploration

`scripts/explore_behavior.py` uses the shared Phase 1.1 loader and validator,
`analytics/behavior.py` for SQL calculations, and `analytics/behavior_report.py`
for Markdown and CSV outputs. A session-ID audit determines whether a global ID
or a customer/session composite key is used consistently across raw and temporary
distinct-row scenarios. Missing session IDs remain in customer and event metrics.

Session-level funnels test event presence and strictly ordered timestamps across
products. Equal-time sequences are ambiguous and reported separately. Purchasing
sessions are anchored at their first purchase event, with UTC-day and repeat-gap
distributions. Horizon tables assess 7/14/30-day coverage without creating labels.
Duplicate group multiplicities support both quality diagnostics and a temporary
distinct-row scenario. No raw data is rewritten or deduplication policy selected.

DuckDB runs with a 2 GB working-memory limit, two threads, disabled insertion-order
preservation (no analysis relies on input order), and a temporary spill directory
cleaned on completion. Intermediate relations stay in DuckDB. Only aggregates
reach Pandas or exported CSV files; customer/session identifiers are not exported.
The main report lives in `docs/reports/`; aggregate CSVs in `data/processed/` are
ignored by Git. Synthetic sequences verify definitions, not just execution.

## Implemented: Phase 1.3A unified persistent dataset

```text
Five immutable local CSVs (October 2019–February 2020)
    → shared CSV validation → raw_events (all rows, source month, UTC time)
        → shared session/funnel SQL → session_summary → sessions view
        → customer and UTC-month aggregations → customer_summary → customers view
        → customer_monthly_summary
        → events_exact_deduplicated (comparison view only)
    → input fingerprint manifest, aggregate CSVs, Markdown build report
```

`scripts/build_dataset.py` orchestrates the build; `ingestion/dataset.py` contains
reusable ingestion and derived-table calculations. The single canonical file is
`data/processed/ecommerce.duckdb`. It uses the existing DuckDB dependency, not a
new database system. Named relations live in the default `main` schema. Rebuilds
are transactional and preserve unrelated objects; failures restore prior tables
and views. A fresh failed build may leave an empty database file, never a partial
published dataset. Source SHA-256 hashes, sizes, and counts identify inputs.

The builder calls the existing `load_events` validator. Both Phase 1.2 and the
builder call `analytics/sessions.py` for session aggregation and funnel logic.
Composite session keys are typed STRUCTs, avoiding hash/concatenation collisions
and a full-file ranking sort. IDs remain strings and session keys are not split
at calendar boundaries. Missing session IDs are excluded only from session
relations; missing customers are excluded only from customer relations. Raw rows
and missing metadata remain intact. Parsed UTC TIMESTAMPs and source YYYY-MM
provenance are separate: monthly customer activity uses event UTC month.

A session with purchases in two months counts in both active-month totals, but
only once in the period total and first-purchase-month distribution. Missing
timestamps cannot establish chronological order or a monthly assignment; explicit
quality columns expose them. Long-lived pairs are retained without inventing an
inactivity timeout. Data-boundary censoring remains an analytical limitation.

Exact comparison groups use all original columns, excluding ingestion metadata.
Groups spanning files receive the earliest source month only in the comparison
view. The builder evaluates this view in a temporary relation for reporting;
all session/customer summaries use raw data. No analytical deduplication choice
is made permanent. The build uses the established 2 GB/two-thread DuckDB resource
settings and temporary disk spill space. Only aggregates are exported to Pandas.
The database and CSV artifacts are ignored by Git; the short measured report is
under `docs/reports/`.

## Implemented: Phase 2.3 customer snapshot feature pipeline

`features/customer_snapshots.py` reads only `raw_events` from the existing database.
Separate historical and future-label SQL stages build one customer row per UTC
prediction date. Historical session counts use exact composite keys over only
window-eligible events, avoiding post-snapshot whole-session leakage. Primary
key and value constraints, independent raw eligibility/label-key reconciliation,
and aggregate temporal audits validate the output before transaction commit.

`features/report.py` reuses Markdown table rendering and exports only aggregated
quality/statistics tables. `scripts/build_customer_features.py` provides the CLI.
The feature and audit tables are the only persistent relations replaced. All
other source and analytical tables remain intact. The 2 GB/two-thread DuckDB
configuration and temporary spill space follow ingestion conventions. Synthetic
boundary, invariance and rollback tests run without the production database.
See [feature definitions](customer-features.md) for missing-ID handling, observed
history limits and reproducible commands. No model training is implemented.

## Implemented: Phase 2.4 provisional chronological baselines

`models/baseline.py` reads the snapshot table through a read-only DuckDB
connection. Inspection precedes training: explicit feature schema/allowlist,
finite nonnegative inputs, unique keys, class balance, distributions and customer
overlap. No raw events enter Pandas. November/December train both baselines;
January validates and February tests. Label windows must end before subsequent
evaluation dates. IDs and dates cannot enter the estimators.

Training-only log1p/scaling and a fixed logistic regression specification are
compared with a training-prevalence constant model. The frozen thresholds and
budget fractions are evaluated separately on validation and test, including
calibration and expected ranking metrics under cutoff ties. No test results
select settings. `models/report.py` writes Markdown and aggregate CSVs through
`scripts/train_baselines.py`. No database tables, raw files, individual prediction
exports, deployed services or experiment infrastructure are changed. Four dates
are insufficient for a final robust evaluation; the report proposes purged
rolling-origin snapshots and a new future holdout.

ClickHouse is the **target analytical database** for the next infrastructure
phase. DuckDB remains the validated reference implementation; migration and
feature reconciliation against ClickHouse are outside this modeling phase.

## Implemented: Phase 3.1 infrastructure foundation

`compose.yaml` defines an independent `ecommerce-ml` project. The analytics bridge
connects ClickHouse, dbt, Metabase, Airflow and ML. An internal metadata bridge
connects PostgreSQL, Metabase and Airflow; PostgreSQL has no host-published port.
Separate application roles/databases isolate Airflow and Metabase metadata.
Persistent volumes are Compose-scoped. All published ports bind to 127.0.0.1,
with host defaults distinct from AIS. No AIS resources are reused or changed.

At the end of Phase 3.1, ClickHouse was empty apart from its dedicated database. dbt contains
only an infrastructure SQL test; Metabase's built-in ClickHouse driver is used.
Airflow standalone is optional local development infrastructure, with no DAGs;
its metadata is PostgreSQL. ML is an optional execution image that reuses the
package; its host data mount is read-only. These Python environments are separate.
See [infrastructure documentation](infrastructure.md) for versions, credentials,
resource limits, profiles, readiness checks, persistence and operations.

## Implemented: Phase 3.2 reconciled raw history

`ingestion/clickhouse.py` provides authenticated HTTP transport with bounded read
retries and no blind write retries. `reconciliation.py` owns the verified schema,
exact-price normalization, canonical checksums and duplicate profiles.
`migration.py` opens the canonical DuckDB file read-only, streams sequential
50,000-row batches into UUID-scoped MergeTree staging tables, and publishes only
a fully reconciled stage using Atomic RENAME/EXCHANGE. Matching destination data
is a no-op; failed stages never append to the published table. Lost swap
acknowledgements are resolved by UUID, not by another swap.

ClickHouse `ecommerce.raw_events` now holds all historical raw events; DuckDB
remains the byte-identical reference and source of existing analytical/ML feature
tables. Original strings/nulls/duplicates are retained, with UTC DateTime64(6)
and exact Decimal(18,2) added safely. Source-month partitioning and customer /
session / time sorting support later batch transformations without uniqueness
assumptions. See [migration design](clickhouse-migration.md) for normalization,
resource limits, permissions and recovery operations.

Dedicated ingestion, dbt and read-only BI users are provisioned without changing
legacy credentials. dbt reads `ecommerce.raw_events` and writes only in
`ecommerce_analytics`; a source declaration and quality tests are present, but
production session/funnel/customer/feature models are not implemented. Airflow
DAGs, dashboards and further training remain deferred. AIS is untouched.

## Planned: agreed target architecture

```text
Public REES46 CSVs → validated ClickHouse ingestion
    → dbt event/session/funnel and customer snapshot transformations
        → Metabase analytical dashboards
        → Python ML chronological validation and scoring research
    ↔ DuckDB reference counts and feature reconciliation
Airflow → orchestrate validated ingestion/transformations/ML steps
Docker Compose → independent local service/runtime boundary
```

This target replaces the older exploratory Kafka/MLflow roadmap; neither system
is part of the agreed stack or implemented here. Data migration, production dbt
models, dashboards, ingestion/ML DAGs and further training are deliberately later
phases. Preserve UTC event windows, raw duplicate policy and event-based target
definitions when reconciling ClickHouse against DuckDB. Session timeout and
production deduplication decisions remain unresolved.

## Current: Synerise Dashboard V1.0

```text
Pinned Synerise Parquet → native ClickHouse file() bulk import → synerise_raw
    → dbt staging (source-clock strings, no UTC claim)
        → first visit/cart/purchase intermediates → overall customer funnel
        → narrow category/SKU metric intermediates → canonical funnel facts
Amazon Reviews 2023 metadata → external_catalog.amazon_products → Amazon staging
    → deterministic synthetic category dimension → synthetic product dimension
        → display enrichment of canonical facts → Metabase Dashboard V1.0
```

Canonical facts are `fct_synerise_funnel_by_category` and
`fct_synerise_funnel_by_product`. They expose five scalar category levels and the
full hierarchy, eliminating large Metabase joins. The overall funnel remains separate.
Equal-second cart/purchase chronology is accepted (`>=`); these all-time funnels
are not the strict REES46 session funnels. Synthetic labels are display-only.

Metric intermediates normally rebuild from raw staging. The documented one-time
bootstrap reused validated historical metrics; future raw refreshes must use the
default path. Use the local catalog target, one thread and bounded query settings.
ClickHouse remains at 8 GiB container / 6 GiB server. Background merges and the
known global tracker discrepancy require adequate idle headroom before validation.
The disabled legacy dashboard fact remains in ClickHouse pending approved removal.

See the [current validation report](reports/metabase-v1-synerise-refactor.md) for
model dependencies, rebuild commands, preservation evidence and limitations.
Earlier phase sections above describe historical REES46 milestones, not the current
Synerise implementation status. Existing ML features and baselines remain independent.
