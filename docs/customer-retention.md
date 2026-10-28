# Customer purchase retention — V3.0

Implemented and validated 28 October 2026. The dbt implementation introduces no ML features or training. The existing
Metabase Customer Retention tab is documented separately in the
[V3 saved-card SQL guide](metabase/v3/README.md). Existing V1.0–V2.2
business logic is unchanged.

## Models and dependencies

All new tables live in `synerise_analytics`, use ordinary MergeTree and have tag
`synerise_retention`. No new ingestion or source declaration is introduced.

| Model | Grain and purpose | Inputs / physical order |
| --- | --- | --- |
| `int_synerise_purchase_dates` | Customer/purchase date; earliest timestamp string on each date | Existing `stg_synerise_product_buy`; ordered client/date |
| `int_synerise_purchase_observation_window` | One shared source-clock envelope with coverage status | Five raw event sources; ordered start date |
| `int_synerise_customer_first_purchase` | Customer; first observed timestamp/date and cohort month | Purchase dates; ordered client |
| `int_synerise_customer_purchase_months` | Customer/calendar purchase month; cohort and month offset | Purchase dates + first purchase; ordered client/month |
| `fct_synerise_customer_monthly_retention` | Eligible cohort/month offset, including zero activity | First purchase + monthly activity + observation envelope; ordered cohort/offset |
| `fct_synerise_customer_repeat_purchase` | Customer; first/last dates, date/month counts, repeat flag, second-date gap | Purchase dates + first purchase; ordered client |

First purchase is the earliest **observed** parseable purchase, not necessarily
first-ever acquisition. Original timestamps are retained as sortable fixed-format
strings (`first_purchase_at`), not labeled UTC. Dates and calendar arithmetic use
the represented source clock, whose timezone remains unverified. The existing
parser supplies validity checks; source timestamp format/parse failures are tested
and must fail validation rather than silently changing the purchasing population.
No invalid timestamps were found in this dataset.

Each customer has one cohort. Monthly retention counts each customer once in each
purchase month, divided by the original cohort size. It is **non-cumulative**:
a customer can skip a month and return later. Month zero equals the eligible
cohort size. Rates are 0–1 fractions for Metabase Percentage formatting.
Purchase-only customers need no preceding page visit or cart.

Repeat purchase means activity on at least two distinct source dates. Multiple
SKU/event rows on one date do not establish a repeat. The optional second-date
elapsed gap is NULL for a single-date customer and positive otherwise. These are
not order counts: no reliable order identifier exists. Daily grouping is a derived
activity grain, not a permanent source deduplication policy.

## Observation-window policy

There is **no authoritative continuous-coverage contract** in the current project.
The supporting window table derives an envelope from min/max original timestamps
across **all five** event types, not purchase timestamps alone. A month with no
purchases can therefore still appear with zero retained customers while another
event source establishes the envelope.

The explicit assumption is continuous collection in strictly interior calendar
months. Every retention row carries:

- `coverage_policy = 'assumed_continuous_interior_months'`
- `coverage_verified = 0`

These rows are eligible under an assumption, **not certified complete observation**.
The first and last envelope months are always excluded conservatively, even if a
boundary happens to land at midnight. Both the cohort month and outcome month
must be interior. Partial cohorts remain in first-purchase/monthly/repeat tables
but are excluded from the retention fact. For this archive, June and December
cohorts are excluded; July–November are reportable under the stated assumption.
Missing retention rows represent ineligible boundary/future periods or offsets
outside the configured horizon, never an eligible zero period. Eligible zero
periods are explicitly generated and filled with `retained_customers=0`.

An envelope does not prove absence of collection gaps. A publisher-supplied
coverage calendar would warrant a separately reviewed policy update. New source
months extend the envelope automatically on rebuild; no calendar month is
hardcoded in production models. Monthly retention cannot distinguish inactivity
from missing collection under this assumption. Empty or malformed source coverage
must be investigated rather than interpreted as zero retention.

## Horizon and operation

`synerise_retention_months` defaults to **12 months after cohort month**: offsets
0 through 12 inclusive. Only eligible observed offsets are produced; 12 does not
mean twelve future months are emitted. Supported configuration is 0–120. Calendar
`addMonths`/`dateDiff('month',...)` handle year boundaries.

Use the existing local environment and dbt setup described in
[operations](dashboard-v1-operations.md); select the `catalog` profile with
`CLICKHOUSE_DATABASE=synerise_analytics` and the configured local HTTP endpoint.
Do not put passwords in commands or files under version control.

```bash
.venv-dbt/bin/dbt parse --project-dir dbt --profiles-dir dbt --target catalog
.venv-dbt/bin/dbt build --project-dir dbt --profiles-dir dbt --target catalog \
  --select tag:synerise_retention --threads 1
.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog \
  --select tag:synerise_retention --threads 1
# Optional horizon override, applied consistently to build and subsequent tests:
.venv-dbt/bin/dbt build --project-dir dbt --profiles-dir dbt --target catalog \
  --select tag:synerise_retention --threads 1 \
  --vars '{synerise_retention_months: 6}'
```

Materializations rebuild only the selected new tables. Rebuild the tagged graph
when sources change; these are not incremental models. The daily intermediate
scans purchase events once for reusable date-grain computation. The envelope
reads all event types once, and downstream models operate on smaller tables.
The `catalog` target retains one thread, a 1 GiB query limit and existing spill
settings. Customer uniqueness uses `unique_in_order`; composite uniqueness tests
use grouping in physical-key order with `optimize_aggregation_in_order=1`.

## Measured validation

The initial scoped build completed **six models and 43 tests** in **7.17 seconds**
(dbt measured execution, excluding startup). An additional adversarial fixture
passed, bringing the V3 suite to **44 tests**. No server settings or dependencies
were changed. Largest build step was the all-source envelope at 3.93 seconds;
daily purchase aggregation took 0.59 seconds. These are local timings, not a
production throughput guarantee; no continuous peak-memory measurement was made.

| Cohort | Customers |
| --- | ---: |
| 2022-06 | 45,950 |
| 2022-07 | 188,877 |
| 2022-08 | 163,009 |
| 2022-09 | 152,962 |
| 2022-10 | 150,009 |
| 2022-11 | 160,629 |
| 2022-12 | 47,774 |
| Total | 909,210 |

All cohort counts match the supplied independent benchmarks.

| July offset | Purchase month | Retained | Rate (fraction) |
| --- | --- | ---: | ---: |
| 0 | 2022-07 | 188,877 | 1.000000 |
| 1 | 2022-08 | 21,156 | 0.112009 |
| 2 | 2022-09 | 17,729 | 0.093865 |
| 3 | 2022-10 | 17,535 | 0.092838 |
| 4 | 2022-11 | 18,047 | 0.095549 |

All July counts and rounded percentages reconcile. Current table sizes:
1,305,284 customer-dates; 909,210 first-purchase customers; 1,140,358 customer-months;
15 eligible cohort/offset cells; 909,210 repeat-summary rows, including **210,633**
repeat purchasers. Shared bounds: **2022-06-23 00:10:00–2022-12-08 00:09:59**, source
clock. Raw purchase events remain 2,318,502.

Tests cover required fields, key uniqueness, source customer reconciliation,
invalid timestamps, single-cohort attribution, nonnegative calendar offsets,
retention/activity agreement, complete eligible grid, partial/future exclusion,
month-zero identity, rates/count bounds, date-count/repeat consistency and NULL
second-date gaps. Small fixtures also cover duplicate rows, an explicit zero
month followed by re-entry, partial boundaries and cross-year arithmetic.

Before/after read-only checks matched protected raw table identities/counts and
all six existing V1/V2 reporting-fact row counts and multiset fingerprints.
No existing model SQL was edited. No dashboard, raw data, credential, REES46 work,
ML pipeline, source file or server limit was changed.

Final release validation passed `dbt parse`, all **44 V3 tests** (1.49 seconds),
and the **full 246-test dbt regression suite** (20.92 seconds), with one thread
and no warnings, errors or skips. Protected source identities/counts and existing
reporting-fact fingerprints still matched the pre-V3 checkpoint. Generated logs
and temporary validation artifacts remain outside the committed files.

## BI and future research

Metabase can use cohort month as row, month number as column and retention fraction
as the heatmap value, showing the assumed-coverage warning. Missing future cells
must remain unavailable, not filled with zero by BI. Repeat summaries describe
observed history and require censoring-aware interpretation.

These models use anonymized original Synerise behavior only, without synthetic
Amazon labels. Any future label enrichment remains display-only. These all-history
tables are **not point-in-time ML features**: a separate strict as-of policy and
validation would be needed before future predictive use. No ML features are built.
