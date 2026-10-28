# V2.2 — Cart Abandonment dashboard reference

## Actual deployment — verified 28 October 2026

V2.2 is deployed in the existing **Synerise funnel analytics** dashboard
(Metabase dashboard ID **2**, `/dashboard/2`), on the **Cart Abandonment** tab
(tab ID **6**). The other tabs remain **Funnel Analytics** and **Time to Conversion**.
No separately named V2.2 dashboard was created. This supersedes the original proposal
for a standalone dashboard, stacked bar and four fixed top-20 ranking cards.

The deployed card SQL, display types, field formatting and parameter mappings were
inspected through **read-only PostgreSQL metadata queries**, without reading sessions
or changing Metabase. This validates saved configuration, not browser-rendered pixels.
The UI integration was completed manually by the user. Repository tooling still has
no UI/API credential or automated dashboard publisher; metadata-database credentials
are not UI/API authentication. Detailed metadata snapshots remain temporary, not Git artifacts.

The tab starts with a text banner explaining first-cart non-conversion versus
session abandonment, a common seven-day-eligible cohort, anonymized source events
and synthetic category/product descriptions.

## Deployed cards

| Card ID | Saved name | Visualization / selected field |
| --- | --- | --- |
| 51 | Eligible Customers — 7-Day Cohort | Number; `eligible_customers_7d` |
| 52 | Non-Conversion Rate — 1 Hour | Number; `abandonment_1h_rate` |
| 53 | Non-Conversion Rate — 24 Hours | Number; `abandonment_24h_rate` |
| 54 | Non-Conversion Rate — 7 Days | Number; `abandonment_7d_rate` |
| 55 | Not Converted Within 7 Days | Number; `abandoned_7d` |
| 56 | Early Share of 7-Day Converters | Number; `early_conversion_share` |
| 57 | First-Cart Customer Conversion Outcomes – 7-Day Cohort | Pie; `outcome` / `outcome_share` |
| 58 | Cart Abandonment by Category | Table; top 100 after filters and selected ranking |
| 59 | Cart Abandonment by Product | Table; top 100 after filters and selected ranking |

All six KPI questions use [overall-cart-nonconversion.sql](overall-cart-nonconversion.sql).
The Number visualization selects the relevant field; no need to create six new
pipelines or sum category/SKU rows. Percentages and shares use **Percentage formatting,
one decimal place**; source values remain **0–1 fractions**. Counts remain integers.
The query also returns overall converter percentiles, but these are not additional
KPI cards on Cart Abandonment; existing timing analytics remain on Time to Conversion.

Overall cards and the pie have **no dashboard parameter mappings**. They intentionally
remain global when category or ranking controls change. Label this behavior clearly;
no category/SKU aggregation is used to manufacture overall distinct customers.

## Conversion outcomes: pie chart, not stacked bar

[overall-conversion-outcomes.sql](overall-conversion-outcomes.sql) returns four rows:
within 1 hour, >1–24 hours, >24 hours–7 days, and not converted within 7 days.
All rows use the same `eligible_customers_7d` denominator. Card 57 is a **pie chart**
with `outcome` as dimension and `outcome_share` as metric. Its legend is enabled,
percentages use one decimal, slice threshold is zero, row sorting is disabled and
the grand total is hidden. The SQL retains `outcome_order` for deterministic results
and `customers` for absolute-count inspection in the underlying question.

This is a deployment change from the proposed stacked bar, not a change in population
or arithmetic. A rounded pie label need not sum to exactly 100.0%. The final slice
includes late purchases and no observed purchase; it is not “never purchased”.
It differs from V2's converter-only timing distribution. Known refresh ordering
behavior remains a presentation limitation; this task did not change it.

## Category and product tables

- Card 58 uses [category-cart-nonconversion.sql](category-cart-nonconversion.sql).
- Card 59 uses [product-cart-nonconversion.sql](product-cart-nonconversion.sql).

The reference SQL bodies match the deployed questions; comments clarify configuration.
Both read one denormalized fact, without dimension joins. The shared **Rank by**
control accepts `rate` (default) or `volume`. It orders by seven-day non-conversion
rate or absolute `abandoned_7d`, with deterministic volume/ID tie-breakers, then
returns **100 rows**. These are two switchable tables, not four separate ranking cards.
Filtering happens before ordering and LIMIT. Local re-sorting of the returned 100
rows does not create a different global ranking: use Rank by to change the SQL order.

Visible category columns: original category ID, synthetic label, hierarchy levels
1–4, eligible cohort, converted 7d, abandoned 7d, abandonment 7d rate and early share.
Visible product columns: SKU, synthetic title, category ID, hierarchy levels 1–4
and the same cohort/conversion fields. Other returned fields are hidden by table
configuration: additional windows/outcomes, level 5/leaf, all-time memberships and
converter-only timing statistics. Those optional fields use different populations
and must not be silently substituted for mature-cohort metrics.

The deployed tables format the shown rates/shares as percentages with one decimal.
No minimum-converter filter applies on this tab: zero seven-day conversions can
legitimately mean 100% non-conversion and NULL early share. Default eligible cohort
100 is a presentation safeguard, not proof of statistical reliability. Rate measures
relative frequency; volume measures absolute impact. Never sum category/SKU memberships
as if they were distinct overall customers. Labels may repeat: original category IDs
and SKUs remain the analytical identifiers.

## Actual filter mappings and defaults

| Dashboard control | Category table 58 | Product table 59 | Overall cards / pie |
| --- | --- | --- | --- |
| Category level 1 | Field Filter on own fact, equality | Same, product fact | Unconnected |
| Category levels 2–4 | Own fact; case-insensitive contains widget | Same, product fact | Unconnected |
| Minimum eligible customers (7 days) | Number `min_eligible_customers`, default **100** | Same | Unconnected |
| Rank by | Text `rank_by`, default **rate**; options rate / volume | Same | Unconnected |

Hierarchy controls have cascading dependencies: level 2 depends on level 1,
level 3 on levels 1–2, and level 4 on levels 1–3. The saved question configuration
uses equality at level 1 and case-insensitive contains matching at levels 2–4;
this is the observed behavior, not a promise of exact matching at every level.
All mappings target columns on the corresponding reporting fact, without SQL aliases.

Dashboard controls for minimum cart customers (default 10) and minimum converted
customers (default 3) exist for other analytics, but are **not connected** to the
Cart Abandonment cards. There are **no standalone category-ID, SKU or date-range
parameters** on these V2.2 questions. IDs are displayed, not dashboard selectors.
Do not add a misleading date filter: the facts are lifetime aggregates without
cohort-date columns. Synthetic hierarchy selectors can cover multiple original
categories without merging their rows.

## Source reuse, validation and limitations

No new dbt model or matching pipeline was needed:

| Source | Grain / purchase matching |
| --- | --- |
| `fct_synerise_time_to_conversion` | Unique first-cart customer; any qualifying purchase |
| `fct_synerise_time_to_conversion_by_category` | Customer × original category; SKU may differ |
| `fct_synerise_time_to_conversion_by_product` | Customer × SKU; same SKU purchase |

All use purchase time >= first cart; no prior page visit or session is required.
Each rate uses its own grain's common seven-day-follow-up cohort. See the
[funnel contract](../../funnel-data-contract.md#cart-non-conversion--v22).

Final parse and **62/62 tests passed on 28 October 2026**, plus executed SQL checks
of both top-100 ranking modes, outcome reconciliation and the supplied category
examples. The [validation report](../../reports/metabase-v1-synerise-refactor.md#v22-final-dashboard-validation--28-october-2026)
records current evidence; the earlier top-20/manual-deployment observations are historical.

Source-clock uncertainty, censoring, unknown logging completeness and missing true
orders/sessions remain limitations. Events are anonymized Synerise source data,
not generated synthetic histories. Amazon-derived titles/category associations
are synthetic display enrichment and remain excluded from ML predictors.
