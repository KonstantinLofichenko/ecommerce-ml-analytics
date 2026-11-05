# E-Commerce ML Analytics

An end-to-end local analytics and machine-learning portfolio built with **ClickHouse,
dbt, Python and Metabase**. It turns anonymized Synerise behavioral events into
customer/category/product funnels, retention reporting and a first-observed-purchase
repeat-purchase dataset, then evaluates chronological Python baselines.

The project covers **225,224,262 behavioral events**, a 1,534,050-row product catalog
and **547,914 eligible ML customers**. Original data stays local and out of Git.
The independently developed REES46/DuckDB analytics and baseline work is preserved.
This is completed offline portfolio work, not a deployed prediction service.

```text
Synerise Parquet → ClickHouse synerise_raw → dbt staging/intermediates
    ├─ canonical funnel/retention facts → existing Metabase analytics
    └─ ml_customer_features → Python baselines → chronological evaluation reports
Amazon metadata → deterministic synthetic display dimensions → analytics facts only
```

The existing **Synerise funnel analytics** dashboard has four documented tabs:
**Funnel Analytics**, **Time to Conversion**, **Cart Abandonment**, and
**Customer Retention**. No prediction writeback or ML dashboard is implemented.
Synthetic Amazon labels are display-only and never enter the ML predictors.

## Final ML baseline results

The target is a purchase on a **later source-calendar date within 30 calendar days**
of first observed purchase, not an order or exact 720-hour outcome. Seven behavioral
features use only the preceding 30 days. The population contains **74,781 positives**.

| Preserved LightGBM experiment | Validation AP | Test AP | Test ROC-AUC | Test Lift@10% | Test Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Interactive notebook | 0.2209 | 0.2134 | 0.6238 | 2.08× | 0.1130 |
| Separate scripted run | 0.2212 | 0.2128 | 0.6269 | 2.06× | 0.1130 |

These are different configurations, not interchangeable reproductions. The
[notebook report](docs/ml_baseline_v4_1.md) verifies saved outputs without rerunning
training. The [scripted report](docs/reports/phase-4.1-repeat-purchase.md) preserves
the executed DummyClassifier, logistic regression and LightGBM comparison.
Discrimination is modest; ranking lift is not demonstrated commercial uplift.
The notebook includes exploratory exposure to test-period labels. A seven-day,
one-fold test and unresolved tracking/timezone assumptions limit generalization.
Future tuning needs a fresh holdout. No additional research is part of finalization.

## Start here

- [Portfolio summary](docs/project-summary.md) and [architecture](docs/architecture.md).
- [Finalization audit and reproducibility checks](docs/reports/project-finalization.md).
- [Notebook setup, kernel and evidence preservation](notebooks/README.md).
- [Scripted reproduction and dependency environments](docs/project-reproduction.md).
- [Feature definitions and validation](docs/customer-features-v4.md),
  [retention](docs/customer-retention.md) and [investigation SQL](sql/analysis/repeat_purchase/README.md).
- [Funnel data contract](docs/funnel-data-contract.md),
  [dashboard operations](docs/dashboard-v1-operations.md), and
  [saved Metabase queries](docs/metabase/README.md).
- [Infrastructure](docs/infrastructure.md), [Amazon import](docs/amazon-catalog.md),
  [synthetic mapping limitations](docs/synthetic-catalog.md), and
  [source provenance/licensing](docs/reports/phase-3.3-synerise-provenance.md).

Canonical reporting facts and display dimensions live in `synerise_analytics`;
`ml_customer_features` is the Python training source. Source-clock timestamps remain
timezone-unverified. Source datasets retain their own licensing/access restrictions;
see the [dataset assessment](docs/reports/phase-3.3-synerise-assessment.md).
Unique historical findings remain indexed in [reports](docs/reports/README.md) and
the [historical archive](docs/archive/README.md). Airflow DAGs, automated deployment,
model serving and rolling evaluation are deliberately outside the completed scope.

## Customer Time to Conversion — V2.0

V2 measures first observed cart → first qualifying purchase (`>=`), regardless of
SKU and without requiring a page visit. V1's overall funnel requires page visit →
qualifying cart → qualifying purchase, so its population is different. Percentiles
use all observed converters; 1-hour/24-hour/7-day cumulative rates share the cohort
with at least seven source-clock days of follow-up. This is not checkout-session
duration, and source timezone remains unverified.

Models build in dependency order:
`int_synerise_customer_first_cart` →
`int_synerise_customer_first_purchase_after_cart` →
`int_synerise_customer_conversion_times` → `fct_synerise_time_to_conversion`.
The conversion-times table retains non-converters with NULL purchase time/duration.
See the [data contract](docs/funnel-data-contract.md#customer-time-to-conversion--v20),
[build/test commands](docs/dashboard-v1-operations.md#v20-build-and-test), and
[dated validation checkpoint](docs/reports/metabase-v1-synerise-refactor.md#v20-validation-checkpoint--27-october-2026).

## Category and product Time to Conversion — V2.1

V2.1 adds per-customer first-cart cohorts within each original category and SKU,
retaining non-converters. New denormalized facts are
`fct_synerise_time_to_conversion_by_category` and
`fct_synerise_time_to_conversion_by_product`. Exact converter-only percentiles and
common seven-day-cohort cumulative rates reconcile with V1's per-grain counts.
These are customer memberships across grains, not additive distinct-customer totals.

See the [definitions](docs/funnel-data-contract.md#category-and-product-time-to-conversion--v21),
[build/test and manual Metabase instructions](docs/dashboard-v1-operations.md#v21-category-and-product-segments),
and [validation](docs/reports/metabase-v1-synerise-refactor.md#v21-segment-validation--27-october-2026).
Both category and product tables are integrated into the existing Time to Conversion
tab, with formatting completed by the user. Join-free reference SQL and filter
instructions remain available for reproduction; overall customer KPI cards remain
unfiltered. Repository finalization does not modify Metabase.

## Technology stack

Python 3.11+, ClickHouse for Synerise storage, dbt for transformations, Pandas for
compact customer features/aggregate results, scikit-learn and LightGBM for offline
models, JupyterLab for preserved exploration, and Metabase for analytics. Pytest,
Ruff, uv dependency management and Docker Compose support reproducibility. DuckDB
remains the REES46 reference. Optional Airflow infrastructure has no implemented DAGs.

## Repository structure

```text
├── README.md
├── pyproject.toml
├── data/
│   ├── raw/                  # Local immutable source CSVs (ignored)
│   └── processed/            # Derived datasets (ignored)
├── dbt/                     # ClickHouse models, macros, schema and singular tests
├── sql/analysis/             # Provenance-labeled investigation SELECTs
├── uv.lock                  # Current project/notebook dependency resolution
├── requirements/            # Historical scripted ML runtime versions
├── docs/architecture.md
├── notebooks/                # Exploratory notebooks
├── scripts/                 # Ingestion, validation, feature builds and training CLIs
├── src/ecommerce_analytics/
│   ├── ingestion/            # Reproducible monthly DuckDB dataset builder
│   ├── analytics/            # Reusable exploratory SQL analysis
│   ├── features/             # Customer snapshots and validation reports
│   └── models/               # Chronological baseline training and evaluation
└── tests/                    # Synthetic fixtures generated at runtime
```

## Local development

From the repository root, with uv and Python 3.11 available:

```bash
uv sync --locked --extra dev --extra ml
uv run --locked --extra dev --extra ml pytest
uv run --locked --extra dev --extra ml ruff check .
uv run --locked --extra dev --extra ml ruff format --check .
```

The historical notebook and its verbatim configuration report are excluded from
automatic lint/format rewriting so their evidence remains unchanged. Python modules
and tests remain checked. No dataset is needed for default synthetic tests; live
migration integration tests require explicit opt-in. Dataset reads, dbt tests and
actual experiment reproduction need the separately configured local services/data.
See [reproduction](docs/project-reproduction.md) for the historical scripted pins,
read-only checks and notebook instructions. Do not rerun the final holdout for tuning.

## Historical REES46 dataset setup

Supply the original REES46 cosmetics CSVs through their authorized dataset source.
Extract a monthly file such
as `2019-Oct.csv` into `data/raw/`. Dataset access and any terms are managed by
the dataset provider; downloading is intentionally manual. Keep original CSVs unchanged.
Do not commit datasets or credentials. Both data directories retain tracked
`.gitkeep` files while their contents are ignored.

## Run exploratory analysis

```bash
python scripts/explore.py --input data/raw/2019-Oct.csv
```

The script analyzes every row using DuckDB SQL and prints event counts, distinct
customers/sessions/products, timestamp bounds, event-type distribution, missing
values for every column, exact duplicate counts, and daily event counts in UTC.
Required columns are `event_time`, `event_type`, `user_id`, `user_session`, and
`product_id`; extra columns are included in missingness and duplicate checks.

IDs and source values are read as strings. Empty fields are missing; literal
strings such as `NULL` or whitespace are not treated as missing. Distinct counts
exclude missing IDs. Timestamp bounds ignore missing times; daily counts include
a null-date group for them. Malformed nonempty timestamps produce a clear error.
Header-only files report zero events; zero-byte, malformed, missing, and
schema-incompatible inputs fail with a nonzero exit code.

Duplicates mean additional occurrences of identical parsed rows across **all**
columns, including missing values. Quoting and line-ending differences do not
make distinct rows. No rows are deleted and source files are never rewritten.

DuckDB materializes the input in a temporary table and performs the aggregations;
the full source never becomes a Pandas DataFrame. DuckDB can spill intermediate
data to disk, so allow adequate local memory and scratch disk for large files.
Terminal output and Pandas frames contain only aggregates (daily results can grow
with the number of dates). Runtime and resource needs depend on file size and
cardinality; no production-scale throughput claim is made yet.

## Phase 1.2: customer behavior and funnel exploration

Analyze the complete October CSV and generate a Markdown report plus aggregate CSVs:

```bash
python scripts/explore_behavior.py --input data/raw/2019-Oct.csv \
  --output data/processed/phase-1.2 \
  --report docs/reports/phase-1.2-october-2019.md
```

Read the [measured October report](docs/reports/phase-1.2-october-2019.md) for
customer purchase frequency, session statistics, presence and chronological
funnels, duplicate impact, 7/14/30-day horizon feasibility, and limitations.
The same command accepts the smaller sample CSV, but use separate output/report
paths to preserve full-month results. Generated outputs are replaced on rerun.

The analysis audits shared session IDs before choosing a key, uses UTC, and
excludes missing session IDs only from session metrics. Funnel stages span
products within a session; chronological progression requires strictly increasing
timestamps. Tie-dependent sequences are counted separately. Purchase events are
not assumed to be orders. Exact duplicates are preserved in the main analysis;
a temporary distinct-row scenario measures their impact without changing raw data.

DuckDB uses a 2 GB working-memory limit, two threads, and temporary disk spill
space. Reserve several GB of free scratch disk; execution time depends on local
resources. Only aggregates enter Pandas. SQL calculations, CSV validation, and
report generation are reusable package functions, separate from the CLI. No
labels, models, or services are created.

## Phase 1.3A: unified October 2019–February 2020 dataset

Place these existing local files in `data/raw/`: `2019-Oct.csv`, `2019-Nov.csv`,
`2019-Dec.csv`, `2020-Jan.csv`, and `2020-Feb.csv`. No download is performed.

```bash
python scripts/build_dataset.py
```

This builds the single database `data/processed/ecommerce.duckdb`, writes
aggregate CSVs to `data/processed/phase-1.3a/`, and generates the
[build report](docs/reports/phase-1.3a-october-2019-february-2020.md).
Use `--raw-dir`, `--database`, `--output`, or `--report` to change locations.
The database and generated CSVs are ignored by Git.

Query the database directly with the existing Python DuckDB dependency:

```python
import duckdb

with duckdb.connect("data/processed/ecommerce.duckdb", read_only=True) as con:
    print(con.sql("SELECT month, count(*) FROM raw_events GROUP BY month ORDER BY month"))
    print(con.sql("SELECT * FROM sessions LIMIT 5"))
```

Persistent relations in the default `main` schema:

| Relation | Purpose |
| --- | --- |
| `raw_events` | Every original parsed row, source `month`, and normalized `event_time_utc` |
| `events_exact_deduplicated` | Exact-row comparison view; never feeds primary summaries |
| `session_summary` / `sessions` | Materialized raw-data session metrics and public view |
| `customer_summary` / `customers` | Observed customer bounds, totals, and five monthly session counts |
| `customer_monthly_summary` | UTC-month activity and first-purchase-month counts |
| `dataset_sources` | Input filenames, SHA-256 fingerprints, sizes, and loaded row counts |

Session identity is always `(user_id, user_session)`, implemented as a STRUCT
rather than concatenated strings or a hash. Sessions span file/month boundaries
and use the same presence/strict chronological funnel definitions as Phase 1.2.
Missing session IDs stay in raw events and customer event counts but cannot form
sessions. Unknown customers cannot form customer summaries; their known session
IDs remain in a NULL-user session group. Timestamped monthly customer counts use
UTC event months, which can differ from input-file provenance. Sessions purchasing
across months count in each active purchase month; first-purchase-month counts
are available separately. Missing-time events remain in total counts.

Rebuilds replace only the named project relations in one transaction; failures
roll back to the prior dataset. Unrelated objects are retained. All original CSV
fields remain strings to preserve identifiers and exact-row comparison semantics.
Normalized times are UTC `TIMESTAMP` values, independent of client timezone.
The build uses 2 GB DuckDB working memory, two threads, and temporary spill space;
reserve several GB of free disk. It may take several minutes. No ML labels,
models, permanent deduplication policy, or additional services are introduced.

## Phase 2.3: customer-level feature snapshots

```bash
python scripts/build_customer_features.py
```

This adds `customer_snapshot_features` and its aggregate build-audit table to the
existing DuckDB database. Four midnight-UTC snapshots (November 2019–February
2020) include prior purchasers, ten historical features and a future 14-day
purchase-event target. Features use only raw events strictly before each date;
labels use [prediction date, prediction date + 14 days). Whole-session summaries
are not used. Existing source and analytical tables are preserved.

See [feature definitions and rebuild instructions](docs/customer-features.md).
The generated [validation report](docs/reports/phase-2.3-features.md) reconciles
supplied Phase 2.1 counts, reports discrepancies, checks nulls and summarizes
features. Close any DBeaver database connection before running the build.
No model training is included.

## Phase 2.4: chronological baseline modeling

```bash
python -m pip install -e '.[dev]'
python scripts/train_baselines.py
```

The pipeline opens DuckDB read-only, inspects the compact customer feature table,
and trains on November/December snapshots. January is validation and February is
test. A training-prevalence constant baseline and logistic regression use a fixed
protocol; log1p/scaling fit only on training data. IDs and dates are excluded as
predictors. The event-based 14-day target is retained.

The [baseline report](docs/reports/phase-2.4-baselines.md) includes feature
inspection, customer overlap, chronology checks, ROC-AUC, Average Precision,
threshold metrics/confusion matrices, top-budget precision/lift, and calibration.
Aggregate CSVs are under `data/processed/phase-2.4/`. Options are `--database`,
`--report`, and `--output`. Models and individual predictions are not exported.
Only four snapshot dates support this provisional evaluation; additional purged
rolling-origin dates and a fresh future holdout are needed before finalizing.
ClickHouse remains the target analytical database for the next infrastructure
phase; this task does not migrate storage or introduce MLflow/deployment.

## Phase 3.1: independent Docker infrastructure

```bash
python3 scripts/init_infra_env.py  # Creates private .env; refuses to overwrite it
docker compose --profile '*' config -q
docker compose --profile tools --profile ml --profile airflow --profile bi build
docker compose --profile bi up -d --wait
docker compose --profile tools run --rm dbt debug
docker compose --profile tools run --rm dbt test
```

Metabase is at `http://127.0.0.1:13000`; ClickHouse HTTP is at port 18123.
Airflow (`--profile airflow`) and Python execution (`--profile ml`) are optional.
The AIS project remains independent. No event data is migrated and no models
are trained by infrastructure startup. See [infrastructure instructions](docs/infrastructure.md)
and the [runtime verification report](docs/archive/infrastructure/phase-3.1-infrastructure.md).

## Phase 3.2: validated ClickHouse raw history

```bash
python scripts/bootstrap_clickhouse.py --generate-missing
python scripts/migrate_clickhouse.py
python scripts/migrate_clickhouse.py --validate-only
docker compose --profile tools run --rm dbt test
```

`ecommerce.raw_events` contains all 20,692,840 reference events with original
strings/nulls/duplicates intact, normalized UTC timestamps and exact decimal
prices. The pipeline reads DuckDB without modification, uses bounded batches and
isolated staging, validates per-month canonical multiset checksums and exact
aggregates, then publishes atomically. Matching reruns insert zero rows.
Restricted ingestion/dbt/BI users avoid raw writes from transformation/BI clients;
the existing Metabase connection is not automatically changed.

Read [migration/recovery instructions](docs/clickhouse-migration.md) and the
[measured report](docs/reports/phase-3.2-migration.md). No sessions, customer
features, production dbt models or ML pipelines are rebuilt in ClickHouse yet.

## Next steps

1. Preserve DuckDB/REES46 reference results and raw-source provenance.
2. Maintain the canonical Synerise dashboard tables and documented memory bounds.
3. Develop leakage-safe Synerise snapshots separately from synthetic display labels.
4. Introduce orchestration only after transformation and recovery protocols are validated.

## Git publication

Never stage datasets, credentials, local databases, virtual environments or generated
logs. Review `git status`, run the checks above and the Dashboard V1.0 dbt checks,
and inspect the staged diff before committing. Use the configured remote without
force-pushing or rewriting history. Example configuration `.env.example` is intentional;
actual `.env` values are private.

## Cart non-conversion reporting — V2.2

V2.2 derives first-cart non-conversion rates/volumes and four timing outcomes from
existing customer/category/SKU facts, without a new model or matching pipeline.
Overall KPIs use unique customers; segmented rankings use per-category/SKU memberships.
Rates remain 0–1 fractions for Metabase Percentage formatting. This is not
session-based cart abandonment, and synthetic labels are not original Synerise names.

[Deployed SQL and dashboard reference](docs/metabase/v22/README.md) document the
existing dashboard’s **Cart Abandonment** tab: six overall KPIs, a four-outcome pie
and two top-100 category/product tables controlled by Rank by and cohort/hierarchy
filters. Percentages display with one decimal. Deployment was completed manually;
read-only metadata verification on 28 October 2026 confirmed the saved configuration.
Repository finalization does not edit Metabase. Existing business definitions are preserved.
See the [contract](docs/funnel-data-contract.md#cart-non-conversion--v22) for denominator,
cohort and source-data limitations.

Metabase question reproduction: [V1.0/V2.0 recovered SQL and validation](docs/metabase/README.md).

V3.0 customer retention: [customer purchase retention models, coverage policy and validation](docs/customer-retention.md).

V4.0 data preparation: [first-purchase behavioral features and validation](docs/customer-features-v4.md).

V4.1 experiment: [chronological repeat-purchase model results and reproduction](docs/reports/phase-4.1-repeat-purchase.md).

Interactive V4.1 notebook: [setup and preservation notes](notebooks/README.md) and
[saved notebook baseline results](docs/ml_baseline_v4_1.md). These results are distinct
from the earlier scripted V4.1 experiment.
