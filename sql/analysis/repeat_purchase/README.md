# Synerise repeat-purchase investigation SQL

Recovered and organized **30 October 2026**. This is a read-only investigation
collection, not another transformation pipeline. It preserves SQL actually found
in local development artifacts, compiled dbt validations and ClickHouse query
history. Production models, Python training code and dashboards were not edited.

The current analytical table is **`synerise_analytics.ml_customer_features`**.
Its earlier name, `ml_customer_features_v4`, was retired after a tested rename.
Queries targeting that old table have been updated to the current identifier;
this is a naming adaptation, not a new population or target definition.

## Execution order and provenance

Run final files in numerical order as needed; they are independent SELECTs and
create no tables. Existing V3/V4 analytical tables must already exist. Files 08
and 14 are optional recomputation checks, not prerequisites for the other files.
Do **not** include `historical/` in an automated acceptance run.

| File | Purpose | Recovered source |
| --- | --- | --- |
| [01](01_page_visit_daily_coverage.sql) | Page visits: daily counts, valid bounds, timestamp/offset checks | Executed local `/tmp/v4_coverage.py` |
| [02](02_add_to_cart_daily_coverage.sql) | Cart additions: daily coverage | Same executed coverage script |
| [03](03_remove_from_cart_daily_coverage.sql) | Cart removals: daily coverage | Same executed coverage script |
| [04](04_search_query_daily_coverage.sql) | Searches: daily coverage | Same executed coverage script |
| [05](05_product_buy_daily_coverage.sql) | Purchases: daily coverage and target tail | Same executed coverage script |
| [06](06_behavioral_source_schema.sql) | Actual customer/timestamp/page-key types | Query log, October 29 |
| [07](07_eligible_population_and_calendar_target.sql) | Eligible customers and calendar-date targets from V3 summaries | Query log, October 29 |
| [08](08_pre_purchase_behavior_features.sql) | Final strict-window, raw-preserving feature derivation | Current compiled `int_customer_behavior_30d` SELECT |
| [09](09_feature_dataset_quality.sql) | Final table counts, keys, NULLs, counts and flags | Query log, October 30 |
| [10](10_mutually_exclusive_activity_groups.sql) | Final three-group populations and targets | Query log, October 29, after flag correction |
| [11](11_fixed_historical_benchmarks.sql) | Fixed historical exact-count acceptance | Compiled `v4_historical_benchmarks` dbt test |
| [12](12_population_and_target_reconciliation.sql) | Final table versus reused V3 eligibility/target | Compiled `v4_population_and_target` test |
| [13](13_strict_lookback_window_audit.sql) | Contributing timestamp bounds and missing eligible anchors | Compiled `v4_window_audit` test |
| [14](14_raw_feature_sample_reconciliation.sql) | Five feature counts versus raw events for 32 deterministic customers | Compiled `v4_raw_sample_reconciliation` test |
| [15](15_customer_history_and_target_coverage.sql) | Left truncation, early cohort and right-censoring checks | Query log, October 29 |
| [16](16_late_customer_censoring_null_safe.sql) | Corrected NULL-safe count of late customers without observed positives | Query log, October 29 |
| [17](17_removal_only_activity_diagnostic.sql) | Resolve additions versus removal-only cart interpretation | Query log, October 29 |
| [18](18_approved_split_maturity.sql) | Approved train/validation/test populations and label maturity | Query log, October 30 |

Headers identify the recovery source and status. Query-log event times are copied
as logged, not reinterpreted as customer-local dates. The current compiled SQL was
obtained from `dbt/target/compiled/ecommerce_analytics/`; only the SELECT text is
preserved here, not generated build logs or materialization statements. Its
maintained source lives in the project's dbt models/macros/tests.

Representation changes are limited to purpose/provenance comments, whitespace,
a terminating semicolon, removal of client-appended `FORMAT JSON`, and replacement
of the retired feature-table identifier. The five coverage queries expand the
original Python loop's table-name substitution; their aggregation logic is unchanged.
No missing exploration was invented to complete a narrative.

## Final validated definitions and findings

First observed purchase eligibility:

- Inclusive start: `2022-07-23 00:12:25`.
- Exclusive end: `2022-11-08 00:00:00`.
- UTC is the explicit **computational parsing convention**, not verified source timezone.

`target_30d=1` means a purchase on a **later calendar date**, with a distinct-date
gap from 1 through 30 inclusive. It is not an exact 720-hour interval and purchase
rows are not orders. V3's second-distinct-purchase-date summary supplies this target.

Behavior uses `[first_purchase_ts - INTERVAL 30 DAY, first_purchase_ts)`.
Equal-time and later events cannot contribute. Event counts preserve source row
multiplicity; exact distinct `page_visit.url` values supply unique pages. The URL
field is an anonymized Int64 page key, not a SKU mapping or decoded web address.

| Mutually exclusive group | Customers | Positive targets | Negative targets |
| --- | ---: | ---: | ---: |
| At least one cart addition | 325,699 | 51,784 | 273,915 |
| Other recorded behavior, no cart additions | 48,901 | 6,475 | 42,426 |
| No recorded behavioral activity | 173,314 | 16,522 | 156,792 |
| **Total** | **547,914** | **74,781** | **473,133** |

Overall target rate: **13.6483%**, rounded to **13.65%**. The cart flag means
`cart_adds_30d > 0`. Removal-only customers are in the other-behavior group; their
removal counts remain available. Final model zero-fills customers absent from the
active-customer intermediate. Queries 11–14 return **zero rows on success**;
other final queries report aggregates or, in 08, customer-level derived features.
Do not commit customer-level results.

### Historical coverage

All five event types contain events on **169 consecutive dates**, June 23 through
December 8, 2022, without whole-day gaps. The first and last dates are partial.
Earliest/latest original values measured in the earlier executed coverage scan:

| Source | Earliest | Latest |
| --- | --- | --- |
| page_visit | 2022-06-23 00:10:00 | 2022-12-08 00:09:59 |
| add_to_cart | 2022-06-23 00:10:20 | 2022-12-08 00:09:55 |
| remove_from_cart | 2022-06-23 00:12:25 | 2022-12-08 00:09:40 |
| search_query | 2022-06-23 00:10:00 | 2022-12-08 00:09:55 |
| product_buy | 2022-06-23 00:12:15 | 2022-12-08 00:09:15 |

The original Python coverage script computed missing calendar dates and summary
extrema from the daily SQL output. That gap calculation was **Python**, not a
separately recovered SQL query; no fabricated historical gap SQL is supplied.
The daily files themselves return observed dates, not synthetic zero-date rows.

No invalid formats, unparseable values or explicit UTC offsets were found. Purchase
records include 21,906 events on December 7 and 24 events on December 8. All
547,914 customers' lookbacks fit the shared behavioral envelope; this includes
160,031 first purchasers from July 23 through August 22. The earliest actual
lookback starts June 23 at 00:15:50, after all four behavioral source minima.

The latest eligible first purchase is November 7. Its inclusive day +30 is
December 7; a negative becomes knowable on December 8 midnight. There are **zero
boundary-right-censored customers in the current V4 population**, conditional on
continuous collection. Among excluded customers first purchasing November 8 or
later, 175,383 lack full follow-up; 16,414 already have observed positive outcomes,
while **158,969** have unresolved negative outcomes. Query 16 recovers that latter
NULL-safe count; it does not relabel customers or alter V4 eligibility.

Daily activity cannot certify complete tracking within a day or for an individual.
Source timezone/DST treatment remains unverified. Therefore retain the current
population under the documented continuous-coverage/source-clock assumptions,
without claiming publisher-certified complete UTC observation.

### Connection to V4.1 training

Query 18 preserves the approved split investigation and its original
`proposed_revised_*` output labels. These boundaries were subsequently approved:
122,467 training customers (July 23–August 15), 78,700 validation customers
(September 15–30), and 33,020 test customers (November 1–7). The temporal gaps
exclude 313,727 customers. Latest negative-label availability is September 15,
October 31 and December 8 respectively, based on first purchase date +31 midnight.
No training code or thresholds are changed by this SQL organization.

## Superseded and incorrect investigation paths

| Historical file | Why it is not a final acceptance query |
| --- | --- |
| [19: cart additions OR removals](historical/19_superseded_cart_add_or_remove_features.sql) | Actual initial compiled feature SELECT from `/tmp/v4-compile.log`. The flag included removal-only customers, conflicting with the supplied benchmark. |
| [20: early group check](historical/20_early_group_check.sql) | Actual executed group SELECT against the earlier, inconsistent materialized feature table. Its SQL was not itself wrong; the underlying flag definition was. |
| [21: nullable censoring error](historical/21_incorrect_nullable_censoring.sql) | Actual earlier query used `NOT (gap BETWEEN 1 AND 30)`; NULL gaps remained NULL and were excluded by `countIf`. Use 16 instead. |

The initial OR-based flag produced 329,269 cart customers / 52,293 positives and
45,331 other-behavior customers / 5,966 positives. There are **3,570 removal-only
customers**, explaining the discrepancy. The no-behavior group did not change.
The earlier nullable censoring query incorrectly reported zero customers without
observed positives; the corrected query reports 158,969.

Historical materialized tables were replaced/dropped during the earlier approved
fix and rename. Running file 20 against today's table returns today's corrected
groups, **not** the earlier bad counts. File 19 preserves the old derivation but
is an expensive optional diagnostic; it must never be published as final features.
The initial non-spilling execution also hit the 1 GiB query cap; this was a resource
failure, not evidence of duplicate IDs or a different eligible population.

## What could not be recovered

- The original author's manual SQL that supplied the task's 547,914 / 74,781
  benchmark was not present in the inspected repository or local artifacts. File
  07 is our actual executed reconciliation against reused V3 models, not an
  assertion that we recovered that external original query.
- No separate saved historical SQL proves UTC, uninterrupted collection, real
  first-ever customer acquisition, or page-to-product identity. These remain
  limitations; timestamp parsing is not such proof.
- The removed early feature-table snapshot is unavailable. Actual query text and
  measured prior findings are retained, but its former data state is not recreated.
- No additional unpersisted UI/editor queries can be established from the available
  history. Git history contained no committed V4 investigation SQL collection.

## Running and validation status

Use the existing authenticated ClickHouse connection in DBeaver or another SQL
client. Do not place credentials in these files or in command-line URLs. Source
scans and optional recomputations can be expensive: use one thread and existing
1 GiB query/external aggregation settings. For file 08 (and historical 19 if
explicitly needed), use `join_algorithm='grace_hash'` and
`grace_hash_join_initial_buckets=16`, matching the successful model's per-query
settings. Settings are runtime controls, not changes to analytical definitions.
No server resource limit increase is required.

On 30 October 2026, **all 21 files passed ClickHouse `EXPLAIN SYNTAX`**. Final files
07, 09–13 and 15–18 were re-executed successfully: population/group counts matched,
quality counters were zero, and benchmark/reconciliation/window assertions returned
no rows. The five raw coverage SELECTs had been fully executed during the preceding
coverage investigation; they were syntax-checked, not rescanned during organization.
Files 08/14 retain prior model-build/dbt-test execution evidence and were not
recomputed now. Historical files were syntax-checked only, not endorsed as correct.

See [feature definitions](../../../docs/customer-features-v4.md),
[dbt macro](../../../dbt/macros/customer_features.sql),
[final feature model](../../../dbt/models/ml/ml_customer_features.sql),
[historical benchmark test](../../../dbt/tests/customer_features_v4/v4_historical_benchmarks.sql)
and [V4.1 experiment](../../../docs/reports/phase-4.1-repeat-purchase.md).
This collection is documentation only; no model, raw table, trained artifact,
dashboard, benchmark definition, commit or push was changed.
