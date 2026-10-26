# Funnel Analytics V1.0 — data contract

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

The canonical product fact built under the unchanged 8 GiB container / 6 GiB server
limits. The existing global memory-tracker discrepancy remains unresolved. Default
full-history metric rebuild performance was not established by the display-only
refactor. These limitations do not change the validated V1.0 definitions or counts.
