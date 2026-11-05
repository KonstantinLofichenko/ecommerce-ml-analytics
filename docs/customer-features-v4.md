# V4.0 — First-purchase customer features

Predict a purchase on a **later source-calendar date**, no more than 30 calendar
days after the first observed purchase date. This is not an exact 720-hour target.
No model training or additional Python pipeline is introduced.

## Models and reuse

- `int_customer_behavior_30d`: one row per eligible customer with at least one
  qualifying behavioral event. It aggregates original page, cart-add, cart-remove
  and search events using an ALL-preserving inner join. Min/max behavioral
  timestamps are audit columns only, excluded from the final feature dataset.
- `ml_customer_features`: one row per eligible customer, including customers
  without behavior. Left-joined missing counts/flags are zero-filled.

Both are MergeTree tables ordered by `client_id` in `synerise_analytics`, tagged
`customer_features_v4`. The shared `customer_features_population` macro reuses
`int_synerise_customer_first_purchase` and
`fct_synerise_customer_repeat_purchase`. There was no existing V4 eligibility or
target table in the repository or database. No V3 model was changed. The target
uses the validated second-distinct-date gap, not purchase event multiplicity.

Eligibility is `first_purchase_ts >= 2022-07-23 00:12:25` and
`first_purchase_ts < 2022-11-08 00:00:00`, parsed explicitly in UTC. The variables
`v4_eligibility_start` and `v4_eligibility_end` override these fixed experimental
bounds. They do not automatically certify source coverage for new data.

## Features and clock policy

Every behavioral event must satisfy the inclusive lower and exclusive upper bound:
`[first_purchase_ts - INTERVAL 30 DAY, first_purchase_ts)`. Events at first purchase
are excluded. Duplicate source rows are retained in event counts. Distinct pages
use exact distinct counting, not approximate hashes.

| Column | Meaning |
| --- | --- |
| `page_views_30d` | Raw qualifying `page_visit` rows |
| `unique_pages_30d` | Distinct original `page_visit.url` Int64 identifiers |
| `cart_adds_30d` | Raw qualifying `add_to_cart` rows |
| `cart_removals_30d` | Raw qualifying `remove_from_cart` rows |
| `searches_30d` | Raw qualifying `search_query` rows |
| `has_cart_activity_30d` | At least one cart addition (validated population definition) |
| `has_behavioral_activity_30d` | At least one event in these four sources |

The inspected `page_visit` schema has `client_id Int64`, `timestamp String`,
`url Int64`. The existing staging model maps `url` to `page_id`. It is a usable
anonymized page key, not a decoded URL, SKU, session or verified real-world page
identity. Other event sources have the same identifier/timestamp types. No page
identifier was invented from row numbers or timestamps.

Explicit `parseDateTimeBestEffort(..., 'UTC')` makes computational lookbacks
consistent across sources and server timezone settings. The publisher's actual
source timezone remains **unverified**: UTC here is an experimental interpretation,
not a newly verified source fact. Target dates reuse V3's represented calendar
dates. The V3 coverage assumption and first-observed-history limitation remain.

`client_id`, purchase timestamp/month and target are identifiers/metadata/label,
not automatically selected predictors. Behavioral features do not use later
purchases, whole-session summaries, synthetic Amazon labels or target values.

## Execution and tests

Use the existing catalog-profile environment setup from
[operations](dashboard-v1-operations.md). From the repository root:

```bash
.venv-dbt/bin/dbt compile --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_customer_behavior_30d ml_customer_features
.venv-dbt/bin/dbt run --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_customer_behavior_30d ml_customer_features --threads 1
.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog \
  --select tag:customer_features_v4 --exclude tag:customer_features_v4_historical --threads 1
.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog \
  --select tag:customer_features_v4_historical --threads 1
```

The two prerequisites above must already be built; the documented V3 build tag
rebuilds them when source data changes. The V4 selection deliberately does not
rebuild V1–V3 models or raw data. Generic tests cover identifiers, nulls, binary
flags, population/target agreement, zero filling, feature relationships and event
bounds. Synthetic boundary fixtures check duplicate preservation, exact lower
inclusion and anchor exclusion. Fixed historical counts have a separate test tag;
exclude or replace those assertions when changing the experimental population.

The first build exceeded the unchanged 1 GiB query limit. The behavioral model
uses a per-query `grace_hash` join with 16 initial buckets to permit disk spill;
this retains all qualifying event rows and does not increase any resource limit.

The benchmark defines cart activity as additions only. Including removal-only
customers initially gave 329,269 cart customers rather than 325,699. The 3,570
removal-only customers belong to the other-activity group; their removal counts
remain intact. This interpretation was resolved by measured benchmark reconciliation.

## Validation — 29 October 2026

Both models compiled and built successfully under the existing one-thread/1 GiB
query profile with disk spill. All **35 tests passed** (34 generic checks and one
fixed historical benchmark), with no warnings or skips. The final model build
completed in approximately 30 seconds locally; test execution took 1.11 seconds.
These are measured local runtimes, not a throughput or continuous peak-memory claim.

| Group | Customers | Repeat purchasers |
| --- | ---: | ---: |
| Cart additions | 325,699 | 51,784 |
| Other activity, no cart additions | 48,901 | 6,475 |
| No behavioral activity | 173,314 | 16,522 |
| Total | 547,914 | 74,781 |

The target rate is **13.6483%**, rounding to 13.65%. Exact counts reconcile with
all supplied references. Keys are unique, required fields nonnull, flags binary,
and contributing event extrema fall inside each customer's strict lookback.
A deterministic 32-customer raw-event sample also matches all five count features;
synthetic tests cover exact lookback boundaries, duplicates, same-date exclusion,
and target gaps of 1, 30 and 31 days.

The initially broad cart-activity interpretation was corrected as documented
above; no remaining benchmark discrepancy exists. No source data or existing dbt
model was modified. Protected raw table identities/counts and existing V1–V2.2
reporting-fact fingerprints match the prior checkpoint. No Metabase cards,
credentials, resource limits, models for training, commits or pushes were changed.
