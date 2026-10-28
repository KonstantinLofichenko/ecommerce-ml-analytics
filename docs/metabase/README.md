# Metabase SQL recovery — Funnel Analytics V1.0 and V2.0

Read-only recovery and validation: **28 October 2026**. Dashboard **2**, “Synerise
funnel analytics”. No saved question, dashboard, dbt model or source was changed.
SQL below reproduces existing metrics; it does not redesign the dashboard.

**Recovered** means the exact native SQL string stored in the saved question.
**Reconstructed** means equivalent SQL derived from saved GUI/MBQL definitions,
resolved table/field metadata and the current reporting facts. It is not a copy
of Metabase's generated SQL. No query below is classified Unverified.

## Card index

| Tab / card ID and exact title | SQL | Source in `synerise_analytics` | Grain / provenance |
| --- | --- | --- | --- |
| Funnel Analytics (4), 38 — Synerise — Customer Conversion Funnel | [Overall funnel](v1/overall-funnel.sql) | `fct_synerise_funnel` | One row per stage; Reconstructed |
| Funnel Analytics (4), 42 — Synerise — Funnel By Category | [Category funnel](v1/category-funnel.sql) | `fct_synerise_funnel_by_category` | One row per original category, top ten by carts; Reconstructed |
| Funnel Analytics (4), 43 — Synerise — Funnel By Product | [Product funnel](v1/product-funnel.sql) | `fct_synerise_funnel_by_product` | One row per original SKU, top ten by carts; Reconstructed |
| Time to Conversion (5), 45 — Synerise — Median Time to Purchase (P50) minutes | [Median](v2/median-conversion-minutes.sql) | `fct_synerise_time_to_conversion` | Customer-scope scalar; Recovered |
| Time to Conversion (5), 47 — Synerise — 75th Percentile Time to Purchase (P75) hours | [P75](v2/p75-conversion-hours.sql) | Same customer summary | Customer-scope scalar; Recovered |
| Time to Conversion (5), 48 — Synerise — 90th Percentile Time to Purchase (P90) days | [P90](v2/p90-conversion-days.sql) | Same customer summary | Customer-scope scalar; Recovered |
| Time to Conversion (5), 44 — Synerise — Cumulative Conversion by Time Window | [Cumulative rates](v2/cumulative-conversion.sql) | Same customer summary | One row per horizon, assuming one summary row; Recovered |
| Time to Conversion (5), 46 — Synerise — Conversion Time Distribution | [Distribution](v2/conversion-time-distribution.sql) | `int_synerise_customer_conversion_times` | One row per observed converter bucket; Recovered |

Cards 49/50 share tab 5 but belong to **V2.1**, not original customer V2.0:
[category TTC](v21/time-to-conversion-by-category.sql) and
[product TTC](v21/time-to-conversion-by-product.sql). The separate
[V2.2 guide](v22/README.md) covers abandonment and mature-cohort outcomes.
Neither implementation was changed here. No other original V2.0 analytical card
was found among the current saved cards on tab 5; deleted historical cards cannot
be established from this inventory.

## Definitions and populations

The [funnel data contract](../funnel-data-contract.md) is authoritative for dbt
business definitions. V1 overall counts customers with a page visit, then a cart
at or after their first visit, then a purchase at or after that qualifying cart.
These are customer-level matches across products, not sessions or orders.
Step rates divide by the previous stage, overall rates by page-visit customers.
Category and SKU facts instead start from customers with a cart in that grain;
purchases qualify at or after the first cart in the same category or SKU.
Category purchases may involve a different SKU in the same category. Customers
can belong to multiple grains; summing those memberships is not an overall funnel.
Their rates divide purchase customers by cart customers, with NULL for zero
denominators. The recovered cards select precomputed facts without new division.

V2 starts with **all first-cart customers**, including customers outside V1's
page-led cohort. Percentiles and the distribution use **all observed converters**.
Cumulative rates instead use the **same seven-day-eligible first-cart cohort** for
all three horizons. The cutoff is first cart at or before dataset end minus seven
days; qualifying elapsed times are inclusive at 1h/24h/7d. Never substitute all
converter counts as mature-cohort numerators. The fourth distribution bucket is
observed conversions after seven days, not customers who failed to convert in
seven days. Slow and unobserved conversions remain subject to end-of-file censoring.

Source coverage is 23 June–8 December 2022, with partial boundary days and
unverified source timezone. Source-clock chronology is not verified physical UTC.
Equal source timestamps can qualify in these established non-strict funnels.
Raw duplicates remain; customer-based facts do not count repeated rows as orders.
Synerise events, IDs and anonymized price buckets are original attributes. Amazon
product titles/category hierarchies are deterministic **synthetic display labels**;
they neither establish real product identity nor justify category demand claims
or ML features. Page visits have no verified SKU/category attribution. Read the
contract for source-clock, censoring, hierarchy fallback and enrichment limitations.

## Reproducing V1 cards and filters

Create native SQL questions only if separately authorized; these files alone do
not change Metabase. Select the ClickHouse connection with access to
`synerise_analytics`. GUI questions originally selected the complete source table:
the SQL uses `SELECT *`, including columns hidden by visualization settings.
Cards 42/43 sort descending by `cart_customers`, limit **10**, and have no secondary
tie-breaker. Card 38 has no explicit sort or limit; use `stage_order` ascending when
configuring a new visualization, noting this is not an explicit saved MBQL sort.

For each optional `category_level_1` through `category_level_4` variable in the
reconstructed segmented SQL, choose **Field Filter**, map to the identically named
column on its source table, use equality/category selection, and leave table alias
blank. The `[[AND {{...}}]]` syntax allows absent filters. Filter before the top-ten
limit. The original cards have no native template tags: these variables are the
native-SQL equivalents of GUI dashboard field mappings.

| Level | Dashboard parameter ID | Category field ID (table 25) | Product field ID (table 26) |
| --- | --- | --- | --- |
| 1 | `d63c91b6` | 222 | 200 |
| 2 | `7facf743` | 223 | 201 |
| 3 | `3cea7a12` | 224 | 202 |
| 4 | `423900e5` | 225 | 203 |

Dashboard controls are `string/=` lists. Level 2's values depend on level 1;
level 3 depends on levels 1–2; level 4 depends on levels 1–3. Map equivalent new
questions to those controls if reproducing the dashboard. The overall card and
all five original V2 cards have **no dashboard parameter mappings**. Current
minimum-cart/converter/eligible controls and ranking controls do not filter these
original cards; do not add them based on their presence elsewhere on the dashboard.
Metabase numeric IDs are installation-specific.

Card 38: Funnel visualization, dimension `stage`, metric `customers`. Category
card: Table, show category ID, levels 1–4, rate, carts and purchases; hide path,
label, level 5, depth and leaf. Product card: Table, additionally show SKU, product
title and category leaf. Rates are **0–1 fractions**, format Percentage with one
decimal (field settings 183/189 provide Percentage; card overrides decimals only).
Both saved tables have a color range configured 0–100 despite fractional values;
this is a presentation-scale inconsistency, not evidence of scaled SQL rates.
It is preserved and was not corrected by this recovery.

## Reproducing V2 cards

The five native SQL files preserve the saved strings exactly, including aliases,
rounding and existing query limitations. No template variables or Field Filters
are needed. Scalar cards round to two decimals in SQL: P50 minutes, P75 hours,
P90 days. Cumulative chart: Bar, ordinal `time_window` dimension,
`conversion_rate` metric formatted Percentage. Source `_pct` names still contain
fractions: **do not multiply by 100**. Distribution: Bar, ordinal `time_bucket`
dimension and integer `converted_customers` metric, ordered by `time_order`.

Known original-query limitations, not silently repaired:

- The cumulative query has no `metric_scope` filter and assumes exactly one
  customer summary row. This assumption holds in the validated table today.
- Its final `ORDER BY window_order` does not reliably sort the entire `UNION ALL`
  result in ClickHouse. The live result returned 24h, 1h, 7d. Verify chart ordering
  when reproducing; an enclosing SELECT/order would be a separately reviewed fix,
  not exact recovered SQL.
- Distribution buckets with zero observations are absent rather than synthesized.
  NULL elapsed times cannot represent a measured conversion; the source's validated
  converted rows supply the elapsed interval. SQL does not impute missing values.
- Rates inherit the fact's NULL-safe denominator and rounding policy. Empty/zero
  denominators must remain NULL; no query converts them to zero or 100 percent.

## Read-only validation results

All eight SQL files executed against ClickHouse on 28 October 2026. Optional
Metabase filters were omitted for base SQL execution. Filter metadata was resolved
against actual table/field IDs; representative concrete hierarchy predicates were
also checked in ClickHouse. Metabase's interactive template expansion and visual
rendering were not executed, so no screenshot-equivalence claim is made.

| Check | Measured result |
| --- | --- |
| V1 overall stage counts | 21,993,998 → 2,285,750 → 557,349 |
| Category fact rows / distinct category IDs | 6,880 / 6,880; recovered view returns top 10 |
| Product fact rows / distinct SKUs | 1,444,160 / 1,444,160; recovered view returns top 10 |
| Category/product rate ranges | 0–1; no NULL rates in current cart-active facts |
| V2 first-cart / observed converters | 2,333,463 / 565,203 |
| V2 seven-day-eligible customers | 2,208,140 |
| P50 minutes / P75 hours / P90 days | 7.08 / 1.71 / 12.66 |
| Eligible-cohort 1h / 24h / 7d converters | 391,873 / 436,456 / 470,986 |
| Cumulative rates (stored rounded fractions) | 0.17747 / 0.19766 / 0.21330 |
| All-converter bucket counts, chronological order | 413,987 / 47,327 / 35,805 / 68,084; total 565,203 |

Counts match the corresponding fact definitions and historical V2 references.
No metric discrepancy was found; ordering and color-scale limitations above belong
to the saved configuration. SQL reads existing reporting tables only; no raw rebuild,
dbt refactor, dataset write, dashboard edit, commit or push was performed.

To validate outside Metabase, remove optional `[[...]]` clauses or replace each
with a concrete predicate such as `AND category_level_1 = 'Electronics'` (quote
values safely). Metabase template syntax is not standalone ClickHouse SQL. Run
these SELECTs through the project's authenticated ClickHouse connection; keep
credentials in local environment configuration, never in SQL or URLs. Compare
counts by their corresponding cohort, not by matching similarly named columns.
