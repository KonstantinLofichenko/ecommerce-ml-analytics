# Funnel Analytics V1.0 / V2.0 — data contract

This is the current semantic contract for the Synerise dashboard. It describes
existing SQL; it does not introduce new calculations. Implementation lives in
`dbt/`, with reporting tables in `synerise_analytics`.

## Canonical models and grains

| Model | Grain and purpose | Validated rows |
| --- | --- | ---: |
| `fct_synerise_funnel` | One row per overall customer-funnel stage | 3 |
| `fct_synerise_funnel_by_category` | One row per original category with cart activity | 6,880 |
| `fct_synerise_funnel_by_product` | One row per original SKU with cart activity | 1,444,160 |
| `dim_synerise_categories` | Every original category; synthetic display taxonomy | 6,912 |
| `dim_synerise_products` | Every original SKU; original category/price bucket and synthetic title | 1,534,050 |

A customer means an observed `client_id`, not a verified person or household.
Customers can occur in multiple category/SKU rows. Do not sum those rows and call
the result a distinct-customer total, or compare those sums directly with the
overall customer funnel.

## Overall customer funnel

1. **Page visit:** count distinct customers with any recorded page visit. The
   first-visit intermediate contains one row per customer and their earliest visit.
2. **Add to cart:** for each page-visit customer, select the earliest cart event
   **at or after that first visit**. A cart before the first visit cannot qualify;
   a later cart can. Count each qualifying customer once.
3. **Purchase:** for each qualifying cart customer, select the earliest purchase
   **at or after that qualifying cart**. Count each qualifying customer once.

The joins use customer identity only. Cart and purchase SKUs/categories need not
match. The page event need not describe the product later carted or purchased.
Intermediates are `int_synerise_funnel_first_visit`,
`int_synerise_funnel_first_cart`, and `int_synerise_funnel_first_purchase`.

`step_conversion_rate` divides a stage count by the previous stage count;
`overall_conversion_rate` divides by the initial page-visit customer count.
The first stage divides by itself, yielding 1 when nonzero. Zero denominators
yield NULL. Stage counts are nested cohorts, not raw event counts.

## Category and SKU funnels

These are separate **cart-to-purchase** funnels. Neither requires a page visit.

| Rule | Category funnel | SKU funnel |
| --- | --- | --- |
| Customer grouping | `(client_id, original category_id)` | `(client_id, sku)` |
| Cart anchor | Earliest observed cart in that category | Earliest observed cart for that SKU |
| Conversion | Any purchase in the same category at or after the anchor | Any purchase of the same SKU at or after the anchor |
| Different purchased SKU | Allowed within the same category | Does not qualify |
| `cart_customers` | Distinct customers with a cart in that category | Distinct customers with a cart for that SKU |
| `purchase_customers` | Those cart customers with a qualifying purchase | Those cart customers with a qualifying purchase |

Category membership comes from original product properties, not synthetic Amazon
labels. Category SQL joins cart and purchase SKUs to those properties. A missing
property mapping would exclude that event from category attribution; original
product coverage is checked by the catalog tests. Purchase-only customers do not
enter a cart cohort. A purchase before the first cart does not qualify unless a
purchase also occurs at or after it. The SKU implementation can use the latest
purchase to establish that such a qualifying purchase exists.

For both facts, `conversion_rate = purchase_customers / cart_customers`, using
Float64 fractions without presentation rounding. Zero denominators yield NULL;
only cart-active grains are reported. Format these fractions as percentages in
Metabase; do not multiply stored values by 100.

The narrow materialized metric tables are `int_synerise_category_funnel_metrics`
and `int_synerise_product_funnel_metrics`. Display attributes are joined only
after aggregation. [Operations](dashboard-v1-operations.md) explains default raw
rebuilds and the one-time historical bootstrap.

## Chronology and attribution limits

All three funnels use **`>=`**, accepting equal-second timestamps. They measure
existence of a qualifying sequence on the represented source clock, not causal
attribution or verified physical ordering. No session boundary, inactivity timeout,
conversion deadline or same-day restriction applies. A qualifying purchase may
occur much later within observed coverage. These funnels are not the separate
REES46 strict-session funnels or the 14-day repeat-purchase ML target.

`page_visit.url` is an anonymized URL identifier. There is no verified URL-to-SKU
mapping, so page views cannot supply a product/category view denominator. The
category/SKU facts intentionally start at cart; they do not measure product-view
conversion. The overall funnel is a customer-level sequence across products.

## Source coverage and quality assumptions

The pinned Synerise archive has **225,224,262 behavioral events**, plus
**1,534,050 product-property rows**. Global event bounds are
**2022-06-23 00:10:00–2022-12-08 00:09:59, source clock**. Event types have slightly
different endpoints; the first and last dates are partial. Activity on all 169
source dates does not establish uninterrupted tracking or complete customer history.
Observed absence is not proof of real-world inactivity; coverage boundaries censor
conversions.

- Original timestamp strings have whole-second representation and an unverified
  timezone. Most seconds cluster on multiples of five. No UTC offset, subsecond
  ordering, DST policy or physical elapsed-time interpretation is invented.
- Original signed identifiers, timestamp text and raw duplicate multiplicities
  are retained. Duplicate provenance is unresolved. Source research observed zero
  nulls and parseable timestamps; these are measurements of the pinned files,
  not guarantees about future imports.
- There are no supplied session IDs, order IDs or checkout events. A product-buy
  record is not a verified order. Original prices are anonymized buckets, not
  revenue. Product properties have no point-in-time validity history; this dashboard
  uses their supplied static category mapping.
- The local event count differs from the published 168,900,513-event reference.
  The cause remains unresolved; archive SHA-256 pins the actual research artifact,
  without proving equivalence to the original challenge corpus.
- Source attribution: Universal Behavioral Modeling Dataset © 2025 Synerise SA,
  CC BY-NC 4.0, as recorded in the [source research and license notice](../analysis/synerise/README.md).
  Preserve attribution, analytical-change notices and the NonCommercial restriction;
  the organizer code license does not relicense the data.

The [source assessment](reports/phase-3.3-synerise-assessment.md),
[provenance investigation](reports/phase-3.3-synerise-provenance.md) and
[download manifest](../analysis/synerise/download-manifest.json) retain detailed evidence.
REES46's October 2019–February 2020 UTC history and existing ML work remain separate.

## Synthetic Amazon enrichment

Amazon-derived paths, titles and donor ASIN associations are **synthetic display
assignments**, not recovered Synerise names or verified product matches. Original
SKU, category ID and price bucket remain original anonymized Synerise attributes.

Mapping `amazon_catalog_v1` deterministically selects compatible Amazon donor
hierarchies and titles for fixed inputs. Labels can repeat; donor titles can be
reused. Missing or inconsistent classifications use documented fallbacks/exclusions.
Input changes can change assignments; the mapping is not append-stable.

Exactly five scalar display levels are exposed. Missing tail levels repeat the
last real path element. The full array, actual depth and actual leaf remain intact,
including paths deeper than five. Repeated flattened values are not extra taxonomy
levels. Malformed paths are tested, not repaired with invented labels.

These fields are **excluded from ML predictors**. Read the
[mapping methodology and limitations](synthetic-catalog.md) and
[Amazon import contract](amazon-catalog.md), including its missing original immutable
upstream checksum manifest. Metabase should query canonical facts without large
runtime dimension joins, applying filters before ranking and LIMIT.

## Validation scope

The [Dashboard V1.0 acceptance report](reports/metabase-v1-synerise-refactor.md)
records 91 passing relevant dbt tests, unchanged original-column fingerprints and
business-grain metrics, identifier/coverage checks, donor formula checks, scalar
hierarchy checks and synthetic chronology fixtures. Fingerprints are probabilistic
multiset evidence, supplemented by direct tests; they are not formal proof.

The permanent Synerise raw import used **count-only acceptance**. It did not perform
full source/destination value checksums or duplicate reconciliation. Stronger checks
from earlier private attempts must not be represented as final permanent-load
validation. See the [completed bulk-load report](reports/phase-3.5-synerise-bulk-load.md).

The V1 canonical product fact built under the then-current 8 GiB container / 6 GiB
server limits. V2 finalization uses user-increased 16 GiB container / 12 GiB server
limits; per-query bounds remain unchanged. The existing global memory-tracker discrepancy remains unresolved. Default
full-history metric rebuild performance was not established by the display-only
refactor. These limitations do not change the validated V1.0 definitions or counts.

## Customer Time to Conversion — V2.0

V2 starts at each observed customer's **earliest cart**, with no page-visit
requirement. The first qualifying purchase is the earliest purchase timestamp
**at or after** that cart, regardless of SKU/category. Earlier purchases do not
qualify; a later purchase can. This shares V1's non-strict (`>=`) chronology but
not V1's overall cohort or cart anchor: V1 requires a visit first and can select
a later cart. Category/SKU V1 metrics retain their original grains and definitions.

`int_synerise_customer_conversion_times` has one row per cart customer. A converter
has `converted=1` and `seconds_to_conversion=dateDiff('second', first_cart_time,
first_purchase_time)`. An observed non-converter has `converted=0` and NULL purchase
time and duration; NULL is never replaced with zero. Zero seconds is a valid tied
conversion. No session boundary or conversion deadline is imposed. Elapsed time
to a subsequent purchase is **not necessarily checkout-session duration**.

### Percentiles versus cumulative rates

- **P50/P75/P90:** exact ClickHouse quantiles among **all observed converters**,
  including those with less than seven days of follow-up and conversions after
  seven days. Non-converters are excluded. The reporting table stores rounded
  minutes; presentation uses minutes for P50, hours for P75 and days for P90.
- **Cumulative rates:** all three windows use the **same denominator**,
  `eligible_customers_7d`: customers whose first cart is at or before
  `dataset_end - INTERVAL 7 DAY`. Numerators count those eligible customers whose
  first qualifying purchase occurs within **<=3,600**, **<=86,400**, or
  **<=604,800** source-clock seconds. Eligible non-converters remain in the
  denominator. Counts/rates must increase monotonically from 1 hour to 7 days.
- Despite their `_pct` suffix, `conversion_1h_pct`, `conversion_24h_pct` and
  `conversion_7d_pct` contain **fractions**, rounded to five decimal places.
  Apply percentage formatting in Metabase, without multiplying the stored metric.
  A zero denominator yields NULL.

The hard-coded dataset-end bound is `2022-12-08 00:09:59`, matching the pinned
source's global endpoint; it must be reviewed for any future dataset refresh.
Follow-up eligibility assumes continuous source coverage, not continuous customer
observation. Dataset-end censoring means an observed non-converter may purchase
later. Converter-only percentiles are descriptive of observed conversions, not
survival-adjusted estimates for all customers, and can underrepresent slow returns.

V2 parses strings to ClickHouse `DateTime` using the server context (observed UTC),
with no explicit timezone argument. This is a **computational representation**, not
verification that source strings are UTC. Cutoffs and parsing must use the same
context. Timestamp clustering/ties and unresolved source timezone/DST semantics
mean numeric durations must not be claimed as verified physical elapsed time.
No raw timestamp or V1 model was changed to create this representation.

### Existing Metabase dashboard

The completed **Synerise Funnel Analytics** dashboard contains the original
**Funnel Analytics** tab and the **Time to Conversion** tab:

| Visualization | Population / units |
| --- | --- |
| Median Time to Purchase (P50) | All observed converters; minutes |
| P75 Time to Purchase | All observed converters; hours |
| P90 Time to Purchase | All observed converters; days |
| Cumulative Conversion by Time Window | Common seven-day-follow-up cohort; 1 hour, 24 hours, 7 days |
| Conversion Time Distribution | Observed converters; <=1 hour, >1–24 hours, >24 hours–7 days, >7 days |

Distribution bins use the converter population, not the mature cumulative-rate
cohort. Summary cards use `fct_synerise_time_to_conversion`; customer-level
histories for distribution analysis are in `int_synerise_customer_conversion_times`.
Metabase may reorder cumulative-chart categories after refresh. This is an accepted
presentation-only limitation for this milestone; no sorting fix or dashboard edit
is part of repository finalization.

## Category and product Time to Conversion — V2.1

These are **per-grain first-cart cohorts**, not category filters applied to V2's
single global first-cart anchor. Category histories have one row per
`(category_id, client_id)`; product histories have one per `(sku, client_id)`.
Neither requires a page visit. Category assignment uses original Synerise product
properties, exactly as the V1 category funnel: first cart in a category → first
purchase in that category at or after the cart; purchased SKU may differ.
Product matching requires the same SKU. Original product eligibility is unchanged.

Non-converters remain with `converted=0`, NULL purchase timestamp and NULL elapsed
seconds. All-time conversion counts reconcile to V1 at the original category/SKU
grain. Repeated customers across grains are intentional; summed memberships are
not unique customers and must not be compared to the overall customer funnel.

Reporting models are `fct_synerise_time_to_conversion_by_category` and
`fct_synerise_time_to_conversion_by_product`. They store exact P50/P75/P90 in
**seconds**, plus average seconds, among observed converters only. If no customer
converts, those statistics are NULL, not zero. Presentation converts P50 to minutes,
P75 to hours and P90 to days. Exact quantile semantics match V2's `quantileExactIf`;
V2.1 does not round stored durations or fractions.

Each grain independently defines `eligible_customers_7d` using its first cart
`<= 2022-12-08 00:09:59 - INTERVAL 7 DAY`. That same denominator is used for
`conversion_1h_rate`, `conversion_24h_rate` and `conversion_7d_rate`, with inclusive
elapsed-second thresholds 3,600 / 86,400 / 604,800. Numerators are `converted_1h`,
`converted_24h` and `converted_7d`; all are restricted to this mature cohort.
Non-converters remain in the denominator. Zero denominator means NULL rates.
Converter-only percentiles and mature-cohort rates have different populations.

V2's source-clock representation, timezone uncertainty, tied timestamps, static
product properties, incomplete observation and dataset-end censoring limitations
also apply here. The endpoint is pinned, not inferred as a guarantee of continuous
logging. Catalog paths/titles remain synthetic display-only labels with unchanged
`amazon_catalog_v1` assignments; original IDs define the cohorts. Do not use labels
as ML predictors. Model tables retain all volumes, including zero-conversion and
small-sample grains; minimum-volume filters are presentation guidance only.

See [build/filter instructions](dashboard-v1-operations.md#v21-category-and-product-segments)
and the [existing validation report](reports/metabase-v1-synerise-refactor.md#v21-segment-validation--27-october-2026).

## Cart non-conversion — V2.2

V2.2 reuses the three V2/V2.1 time-to-conversion facts; no matching pipeline or
persistent reporting model is added. “Cart abandonment” is a dashboard shorthand
for **first-cart non-conversion within an elapsed window**, not session abandonment,
verified basket abandonment, cancelled orders or a causal explanation of customer behavior.

Let E be a grain's `eligible_customers_7d` and C1/C24/C7 its cumulative conversion
counts. All counts share that grain's seven-day-follow-up cohort and existing
purchase matching. Customer, category and SKU populations must remain separate.

| Measure | Formula |
| --- | --- |
| Not converted within 1 hour | E − C1 |
| Not converted within 24 hours | E − C24 |
| Not converted within 7 days | E − C7 |
| Non-conversion rate at each horizon | Corresponding count / NULLIF(E, 0) |
| Early conversion share | C1 / NULLIF(C7, 0) |

The four mutually exclusive timing outcomes are C1, C24−C1, C7−C24, E−C7.
They sum to E; their shares each divide by E. Thresholds are inclusive, so exactly
1 hour belongs in the first bucket and exactly 7 days is a conversion within 7 days.
The final bucket includes late purchases and no observed purchase; it does not
establish that a customer will never purchase. Non-conversion counts decrease as
the horizon expands. For zero E, outcome/non-conversion shares are NULL; for zero
C7, early share is NULL. Signed subtraction avoids silently wrapping invalid counts.

Per the chosen Metabase convention, returned rates/shares are **fractions in [0,1]**,
not the task's initially proposed 0–100 percentage-point values. Use Percentage
formatting, without multiplication by 100. Round only for presentation. Existing
converter-only percentiles remain separate and cannot be interpreted as maturity-
adjusted percentiles for the seven-day cohort or all visitors.

The dashboard separates **rate** (relative frequency) from **volume** (absolute
non-conversions). Default segmented minimum is 100 eligible customers; rankings
are calculated after filtering. This cutoff is not a statistical reliability proof.
All category/SKU counts are memberships, so totals across rows are not unique
customer KPIs. Overall cards use the genuine customer fact and stay unconnected
to segment filters. No date filter is supported by these lifetime facts.

Source-clock uncertainty and dataset-end censoring remain unchanged. Original
Synerise events are anonymized source records; synthetic enrichment refers to
Amazon-derived display labels/titles, not invented event histories or proven entity
matches. The actual UI is the **Cart Abandonment** tab of **Synerise funnel analytics**:
six overall KPIs, one four-outcome pie and two switchable top-100 segmented tables.
Only the segmented tables receive hierarchy/minimum-eligible/rank parameters; overall
KPIs and the pie remain global. Fractions display as percentages with one decimal.
See the [deployed dashboard and SQL reference](metabase/v22/README.md).

## Monthly purchase retention — V3.0

See [customer retention](customer-retention.md) for the new customer-cohort,
monthly activity and repeat-date models. Cohorts use first observed purchase,
not the V1 page-led or V2 first-cart population. Retention is non-cumulative,
rates are fractions, and repeat purchasing requires two distinct source dates,
not two event rows or inferred orders. Boundary cohort/outcome months are excluded
from retention; interior coverage remains explicitly assumed, not verified.
Existing V1.0–V2.2 definitions above are unchanged.
