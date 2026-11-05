# Funnel Analytics V1.0 / V2.0 operations and implementation notes

The measured acceptance summary is in the [final validation report](reports/metabase-v1-synerise-refactor.md).
Current semantics are defined in the [funnel data contract](funnel-data-contract.md).
Build guidance below remains applicable; measured timings, card IDs and migration
observations are dated refactor evidence rather than a live dashboard inventory.

## Hierarchy and synthetic semantics

The category dimension owns the hierarchy calculation. It retains the complete
`synthetic_category_path` and exposes exactly five scalar **String** columns,
`category_level_1` through `category_level_5`. For level n, select element
`min(n, length(path))`. Only missing tail positions repeat the last available
label; original labels are unchanged. `category_depth` is the full array length,
and `category_leaf` is its actual final element, including depths six and seven.
The leaf is also a scalar String. All four canonical models have these same types.

Preflight found **zero** empty paths or null/blank elements. Tests reject malformed
paths rather than inserting invented labels. Repeated labels are display
conveniences, not extra real taxonomy levels. The full path is never truncated.

| Actual depth | Categories | Products |
| --- | ---: | ---: |
| 2 | 3,228 | 672,252 |
| 3 | 523 | 119,962 |
| 4 | 1,340 | 311,157 |
| 5 | 1,492 | 368,114 |
| 6 | 297 | 55,207 |
| 7 | 32 | 7,358 |

The distribution is unchanged. Products inherit flattened fields from the category
dimension. Product facts inherit them from the product dimension; category facts
inherit them directly from the category dimension. Mapping policy remains
`amazon_catalog_v1`. Synthetic paths and titles are display enrichment, **not
recovered Synerise attributes or ML predictors**. Existing synthetic provenance,
quality flags and `exclude_from_ml: true` metadata are retained. Facts also identify
synthetic display fields in their metadata.

## Dependencies and repeatable builds

The new narrow tables `int_synerise_product_funnel_metrics` and
`int_synerise_category_funnel_metrics` contain only their business identifier,
cart customers, purchasing customers and conversion rate. Reporting facts attach
hierarchy/title fields **after** aggregation. No new dashboard reporting copy was
created.

Default intermediate builds reproduce the original raw-event SQL through shared
macros: product metrics group customer/SKU, while category metrics group
customer/category using original product properties. Purchases qualify at or after
first cart (`>=`, including equal-second timestamps). A later purchase may be a
different SKU only in the category funnel. Both remain all-time; there is no session,
conversion deadline or page-visit product attribution. Rates remain Float64 fractions.

For this migration only, `synerise_funnel_bootstrap: true` copied the existing
validated fact metrics into those intermediates before the facts were replaced.
It avoided unnecessary raw-event aggregation. **Do not use that variable for future
refreshes or clean deployments**; its input facts must already exist and be validated.
The default path has no dependency on that pre-existing state. The shared raw
macros were executed against adversarial synthetic fixtures; the full historical
raw aggregation was deliberately not rerun just to attach labels. Its future full
refresh runtime/resource behavior has not been established by this migration.

Use the existing authorized credentials exported privately; no passwords belong
in commands or versioned files. The restricted `ecommerce_dbt` account still lacks
Synerise access; this run used the existing administrator without changing grants.

```bash
export CLICKHOUSE_DATABASE=synerise_analytics
export CLICKHOUSE_HOST=127.0.0.1
export CLICKHOUSE_PORT=18123
# CLICKHOUSE_USER / CLICKHOUSE_PASSWORD already exported privately.

# Display-only refresh: reuse existing validated metric intermediates.
.venv-dbt/bin/dbt run --project-dir dbt --profiles-dir dbt --target catalog \
  --select dim_synerise_categories dim_synerise_products \
  fct_synerise_funnel_by_category fct_synerise_funnel_by_product

# When raw events change, or on a clean deployment, FIRST rebuild metrics from raw.
.venv-dbt/bin/dbt run --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_synerise_product_funnel_metrics int_synerise_category_funnel_metrics
# Then run the display-only refresh above.

.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog \
  --select dim_synerise_categories dim_synerise_products \
  fct_synerise_funnel_by_category fct_synerise_funnel_by_product \
  int_synerise_category_funnel_metrics int_synerise_product_funnel_metrics \
  assert_category_hierarchy_examples assert_synthetic_catalog_classification \
  assert_synthetic_catalog_pool assert_synerise_reporting_chronology_examples \
  assert_metabase_v1_baseline
```

No `+` selector is required for display-only changes. On a clean deployment the
existing staging models must be built first. Raw refreshes intentionally changing
the pinned historical release require explicit reconciliation and an update to
`assert_metabase_v1_baseline`; do not silently relax that regression gate.

## Memory and validation

At the V1 refactor, container memory was **8,589,934,592 bytes (8 GiB)** and server memory was
**6,442,450,944 bytes (6 GiB)**. These are historical limits; V2 now uses 16/12 GiB.
CPU allocation remains two CPUs. The catalog
target uses **one dbt thread** and one ClickHouse execution thread, 1 GiB per-query
memory, 64 MiB external aggregation and 32 MiB external sort thresholds. Insert
blocks and join memory are bounded; the product reporting join can spill with
`grace_hash` at 64 MiB. Neither memory limit was increased during that V1 refactor.

Inspection of the installed adapter confirms `custom_settings` are copied into
connection settings. Actual INSERT query-log records independently show
`max_threads=1`, `max_memory_usage=1073741824`, external grouping `67108864` and
external sorting `33554432`. Recorded build-query peak allocations were:

| Model | Query peak bytes |
| --- | ---: |
| dim_synerise_categories | 296,833,322 |
| dim_synerise_products | 387,168,348 |
| fct_synerise_funnel_by_category | 12,749,471 |
| fct_synerise_funnel_by_product | 199,025,652 |

These are per-query peaks, not a continuously sampled global/container peak.
The canonical product build succeeded under the unchanged server limit.

The first suite passed 79/81 checks; two existing catalog checks hit the known
global tracker code 241 during background merges. Bounded joins resolved those
checks, but a subsequent suite hit code 241 in the exact-distinct SKU uniqueness
check. Uniqueness now uses exact **in-order aggregation over the sorted identifier**
with bounded blocks and spill settings. Before the final suite, merges were idle
and tracked memory was approximately 823 MB. **91/91 passed** thereafter.
No restart, cache purge, server setting change or service interruption was used.
The underlying global tracker discrepancy is **not claimed fixed**. Start rebuilds
and tests with idle ingestion/merges and adequate server headroom; bounded query
memory does not eliminate memory used by concurrent work.

Checks cover identifier uniqueness/nulls, exact historical row counts, full source
coverage, real attributes, donor formulas/titles, provenance, forward-fill, leaf,
depth, scalar types, cross-model hierarchy consistency, exact intermediate/fact
metric equality and pinned grain fingerprints. Shared-macro fixtures cover duplicate
cart actions, equal timestamps, purchase-before-cart, different-SKU/same-category
conversion, wrong-category rejection, purchase-only customers and no time deadline.
Ruff lint passed; all 97 Python files passed format checking.

## Metabase query guidance and historical migration observations

During the V1.0 refactor, read-only metadata inspection found these saved SQL questions
requiring migration. The dashboard is now declared complete; the entries below are
historical observations, not outstanding changes or a fresh inspection:

| Card at inspection | Saved name | Migration guidance recorded then |
| --- | --- | --- |
| 39 | Synerise — Funnel by Category | Remove dimension join; select hierarchy directly from the canonical category fact. |
| 40 | Sunerise — Funnel by Product | Remove dimension join; select hierarchy directly from the canonical product fact. |

At that inspection both selected top ten IDs first, then joined the category dimension.
For any future query changes, move
all hierarchy filters **before ORDER BY/LIMIT**, otherwise filtering a preselected
top ten can return incorrect rankings. They referenced canonical facts at the inspection.
At that inspection no saved question definition directly named the legacy dashboard
table. Its Metabase table ID was 27; canonical category/product table IDs were 25/26.
Do not redirect cards 39/40 to new copies or create runtime dimension joins.

Example replacement for card 40:

```sql
SELECT sku, synthetic_product_title, category_id,
       category_level_1, category_level_2, category_level_3,
       category_level_4, category_level_5, category_depth, category_leaf,
       cart_customers, purchase_customers, conversion_rate
FROM synerise_analytics.fct_synerise_funnel_by_product
WHERE 1 = 1
  [[AND {{category_level_1}}]]
  [[AND {{category_level_2}}]]
  [[AND {{category_level_3}}]]
  [[AND {{category_level_4}}]]
  [[AND {{category_level_5}}]]
ORDER BY cart_customers DESC, sku
LIMIT 10
```

Configure each optional variable as a Field Filter mapped to the corresponding
canonical fact field. For card 39 use the category fact and omit SKU/title. Refresh
Metabase's schema metadata manually to discover new columns, format the rate as a
percentage, and configure independent or cascading hierarchy filters as desired.
Keep synthetic-data descriptions visible.

Join-free filtered probes (`Electronics` / `Camera & Photo`, top ten) completed in
**0.086 seconds for products** and **0.003 seconds for categories**, measured via
HTTP on this local server. They returned ten rows each. Product filtering still
scanned all 1,444,160 narrow fact rows because sorting remains by SKU; no claim of
hierarchy-index pruning or cold-cache performance is made.

At refactor validation, `fct_synerise_funnel_by_product_dashboard` remained physically intact,
with its original UUID, 1,444,160 rows and unchanged fingerprint. Its dbt node was
disabled, so normal builds would not perpetuate a duplicate reporting concept.
No dbt model depended on it. This retention statement describes that historical
validation only; the later observation below supersedes its deployment status.

## Repository preparation observation

At the later repository-preparation check, the disabled legacy dashboard relation
was already absent (`EXISTS TABLE` returned 0). No DROP was performed by this task.
Earlier retention statements above describe the refactor-time state, not the later
live state. The canonical facts remain unchanged and validated.

## V2.0 build and test

The existing Metabase dashboard's second tab is completed; do not recreate or edit
it as part of validation. Its refresh-ordering issue is presentation-only. Consult
the [V2 data contract](funnel-data-contract.md#customer-time-to-conversion--v20)
before comparing its first-cart cohort with V1's page-visit-qualified cohort.

With the existing authorized credentials privately exported, use the catalog target
and paths below. Raw models need not be rebuilt merely to test existing tables.

```bash
export CLICKHOUSE_DATABASE=synerise_analytics
export CLICKHOUSE_HOST=127.0.0.1
export CLICKHOUSE_PORT=18123
# CLICKHOUSE_USER and CLICKHOUSE_PASSWORD already exported privately.
.venv-dbt/bin/dbt parse --project-dir dbt --profiles-dir dbt --target catalog

.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_synerise_customer_first_cart \
  int_synerise_customer_first_purchase_after_cart \
  int_synerise_customer_conversion_times fct_synerise_time_to_conversion \
  path:tests/synerise_time_to_conversion --threads 1

# Explicit rebuild only when required; this scans raw cart/purchase histories.
# Not executed during the V2 documentation/validation checkpoint.
.venv-dbt/bin/dbt run --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_synerise_customer_first_cart \
  int_synerise_customer_first_purchase_after_cart \
  int_synerise_customer_conversion_times fct_synerise_time_to_conversion --threads 1
```

Refs enforce build order: first cart, first qualifying purchase, conversion times,
then reporting summary. Models use a 1 GiB query cap and one execution thread;
the original join models used `grace_hash` with a 64 MiB join threshold and raw
grouping used a 256 MiB external aggregation threshold. The later successful
settings-removal experiment below supersedes those model-local controls where noted;
the user increased the container/server allocation for the completed V2 checkpoint.

### Memory-efficient uniqueness and validation history

All three customer tables are sorted by `client_id`. Their uniqueness checks use
exact `GROUP BY client_id HAVING count()>1` with
`optimize_aggregation_in_order=1`, `max_threads=1` and a 1 GiB query cap.
`dbt/macros/tests/unique_in_order.sql` supplies the generic checks on first cart
and first purchase. Conversion times instead uses the single singular test
`dbt/tests/synerise_time_to_conversion/assert_synerise_customer_conversion_unique.sql`;
it has no redundant generic uniqueness check. The one-row fact retains generic
uniqueness on `metric_scope`.

The final inventory is **20 tests**: 15 model/column checks and five singular tests,
rather than the initially reported 15. Parse passed. All 20 passed on
**27 October 2026 at 06:06:39–06:06:40 Moscow time** (03:06:39–03:06:40 UTC).
The isolated optimized uniqueness test also passed before that suite.

A subsequent attempt failed before tests started in adapter
`list_relations_without_caching`, a metadata aggregation over `system.tables` and
`system.databases`. Query ID `4ea706f7-d71a-4dc6-a534-8a7001e48b14` recorded code 241 and
6,898,548 bytes query memory while the global tracker reported the 6 GiB ceiling.
This did not establish duplicate customers or a metric correctness failure.
Read-only follow-up found no competing active query/mutation, but system metric-log
merges were active. Those current samples do not reconstruct the earlier peak;
the global tracker discrepancy remains unresolved.

The previous pass is accepted as the unchanged-code checkpoint: all 20 successful
server test queries match current compiled SQL; current model texts match the parsed
manifest; all V2 source-file modification times predate that pass; and intervening
parse logs record zero added/deleted/changed files. The suite was not repeatedly
rerun to force a pass. Raw tables, Metabase and resource settings were not changed.
Future runs still require headroom because adapter metadata discovery itself can
hit the global limit before memory-bounded tests execute.

### Current memory allocation and final V2 checkpoint

On **27 October 2026**, the user increased ClickHouse allocation to:

| Scope | Configuration | Verified bytes |
| --- | --- | ---: |
| Docker container | `compose.yaml`, ClickHouse `mem_limit: 16g` | 17,179,869,184 |
| ClickHouse server | `infra/clickhouse/development.xml`, `max_server_memory_usage` | 12,884,901,888 |

Container inspection and `system.server_settings` confirmed both active limits;
Compose configuration validation passed. CPU, credentials, ports, source mounts,
server pools and model query caps were not changed by this checkpoint. The increased
allocation does not establish a root-cause fix for the earlier tracker discrepancy.

The latest existing result artifact records **20/20 tests passing**, one thread,
**0.61 seconds** suite elapsed, completed **27 October 2026 at 06:24:09 Moscow time**
(03:24:09 UTC), after the user increased allocation. Model texts in its manifest
match current files. The earlier pass/failure history above is retained as historical
evidence; it is not the final checkpoint status. No additional whole-suite reruns,
raw-event aggregation rebuilds, service changes or Metabase edits were needed for
finalization. Generated logs and dbt artifacts remain ignored.

## V2.1 category and product segments

Definitions are in the [V2.1 contract](funnel-data-contract.md#category-and-product-time-to-conversion--v21).
This extension adds six tables: two narrow first-cart cohorts, two nullable
conversion histories, and the two denormalized reporting facts. Only new models
are selected; omit `+` to preserve existing parents and historical models.
Use the same private credentials and `catalog` target configuration as V2 above.

```bash
.venv-dbt/bin/dbt parse --project-dir dbt --profiles-dir dbt --target catalog
.venv-dbt/bin/dbt run --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_synerise_category_first_cart int_synerise_product_first_cart \
  int_synerise_category_conversion_times int_synerise_product_conversion_times \
  fct_synerise_time_to_conversion_by_category \
  fct_synerise_time_to_conversion_by_product --threads 1
.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog \
  --select int_synerise_category_first_cart int_synerise_product_first_cart \
  int_synerise_category_conversion_times int_synerise_product_conversion_times \
  fct_synerise_time_to_conversion_by_category fct_synerise_time_to_conversion_by_product \
  int_synerise_customer_first_cart int_synerise_customer_first_purchase_after_cart \
  int_synerise_customer_conversion_times fct_synerise_time_to_conversion \
  path:tests/synerise_segment_conversion path:tests/synerise_time_to_conversion --threads 1
```

Refs enforce dependency order. `synerise_segment_summary` computes raw-second
statistics and unrounded fraction rates from sorted narrow histories. Streaming
composite uniqueness reuses `unique_in_order`; exact aggregation in order bounds
per-grain state. Joins use a 64 MiB grace-hash threshold, query memory is 1 GiB,
external aggregation is 64 MiB and external sort is 32 MiB. Limits are unchanged.
Refresh cohorts before facts if source data changes; update the pinned observation
endpoint and reconcile V1 definitions deliberately rather than bypassing failures.

### Completed Metabase integration and reference filter setup

On 27 October 2026, the user confirmed both tables were added to the existing
Time to Conversion tab and formatting was complete. This is user-confirmed UI
status, not an independent dashboard inspection. The following SQL and setup
instructions are retained for reproduction; no outstanding UI action is implied.

Reference native SQL:

- [Time to Conversion by Category](metabase/v21/time-to-conversion-by-category.sql)
- [Time to Conversion by Product](metabase/v21/time-to-conversion-by-product.sql)

These files contain Metabase optional-variable syntax, not dbt Jinja. Each queries
only its final reporting fact, with no dimension joins. Add both saved questions
to the **existing Time to Conversion tab**, not a new dashboard/tab.

For each question, configure `category_level_1` through `category_level_4` as
**Field Filters**, mapped to the identically named scalar column on that question's
reporting fact, never to the dimension table. Connect the existing dashboard
hierarchy filters to these variables on the two new cards. Cascading filters may
be configured manually. Do **not** connect category filters to the existing overall
customer KPI cards/charts: those remain global and unfiltered.

Set the three minimum-volume variables as basic **Number** parameters. Suggested
starting defaults are `min_cart_customers=100`, `min_converted_customers=30`, and
`min_eligible_customers=100`; these are practical display safeguards, not guarantees
of statistical reliability. Use zero or omit them for complete long-tail exploration.
They are applied before ORDER BY/LIMIT and do not remove data from the dbt models.
A high cart count does not compensate for very few converters; display both cohort
sizes and converter counts alongside duration statistics. Small samples, especially
P90, require caution and may merit higher thresholds for comparisons.

Recommended table columns: original category ID or SKU/title, levels 1–4 and leaf,
cart/converted/eligible customers, P50 minutes, P75 hours, P90 days, and the three
cumulative rates. Optional detail columns include depth, level 5, average hours and
window conversion counts. Format durations to two decimals and rates as percentages
without multiplying the stored fractions by 100. NULL statistics mean no observed
conversion or no eligible denominator, not zero time/rate. Both queries return the
top 100 by converter count after filtering; edit this display limit as needed.
The known Metabase refresh ordering issue is unchanged; no UI edits were performed.

### Final V2.1 settings experiment and publication checkpoint

A later user-requested experiment removed model SQL `SETTINGS` clauses one at a
time, rebuilding and testing each model and comparing complete result fingerprints.
Six passed unchanged: customer first cart, customer first qualifying purchase,
customer conversion times, customer summary, category first cart and product first
cart. Their shared memory/thread bounds now come from the unchanged `catalog`
profile. Customer conversion times keeps `join_use_nulls=1` in dbt `query_settings`
configuration because it controls unmatched-purchase semantics, not just performance.

Removing the category conversion-history settings exceeded the **1 GiB query cap**.
That source was restored; its last successful table remained intact and reconciled
with V1. Remaining SQL settings were not removed. In particular, both segmented
conversion-history models and reporting facts retain their original explicit
controls. No server limit increase or metric-definition change accompanied this
experiment. This is a documented execution limit, not an unresolved duplicate or
conversion-count finding. The earlier initial-build timings remain historical.

After these changes, final parse and **60/60 tests passed in 7.59 seconds**, with
one thread and no errors/skips/warnings. V1 reporting/catalog fingerprints, the V2
customer summary, and protected raw-table UUIDs/counts still match their baselines.
No tables or dashboard objects were rebuilt or changed during final validation.

## V2.2 cart non-conversion questions

The [V2.2 deployed-dashboard reference](metabase/v22/README.md) records the actual
Cart Abandonment tab of **Synerise funnel analytics**, verified read-only on
28 October 2026: six overall Number cards, one four-outcome pie and two top-100
category/product tables with a shared rate/volume Rank by control. The four native
SQL files match saved query bodies. Overall cards and the pie have no parameter
mappings; only segmented tables receive hierarchy, eligible-cohort and rank controls.
Rates/shares use Percentage formatting with one decimal. No standalone category-ID,
SKU or date filter is deployed. Repository tooling has no authenticated UI/API
publisher; the user deployed the dashboard manually. Finalization did not modify it.

Only two singular tests are new; no persistent models or matching logic were added.
Run `dbt parse` as usual, then reuse the complete V2.1 test command above with
`path:tests/cart_nonconversion` added to its selectors. This runs **62 tests** with
`--threads 1`. Existing tests validate the per-grain mature cohorts and uniqueness;
new tests validate partition arithmetic and boundary/zero-denominator behavior.
No `dbt run` or raw-event rebuild is needed for V2.2. SQL queries and generated
temporary validation outputs are kept separate; only reviewed question templates
and tests belong in Git.

## ML reporting tab — 5 November 2026

The existing dashboard now has **ML — Repeat Purchase Prediction** (tab 8),
without changing the V1–V3 tabs. See [ML tab instructions](metabase/ml/README.md)
for its ten saved questions, linked identity filters, unavailable notebook states,
idempotent provisioning and 100-case live query validation. Nine questions use
Query Builder; only score-decile ranking uses native SQL. Refreshing this tab
reads published reporting views and does not train or rebuild anything.
