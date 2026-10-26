# Dashboard V1.0 operations and implementation notes

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

Container memory remains **8,589,934,592 bytes (8 GiB)**, server memory remains
**6,442,450,944 bytes (6 GiB)** and CPU allocation remains two CPUs. The catalog
target uses **one dbt thread** and one ClickHouse execution thread, 1 GiB per-query
memory, 64 MiB external aggregation and 32 MiB external sort thresholds. Insert
blocks and join memory are bounded; the product reporting join can spill with
`grace_hash` at 64 MiB. Neither memory limit was increased.

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
