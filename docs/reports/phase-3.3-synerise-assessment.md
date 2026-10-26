# Phase 3.3 — Synerise RecSys 2025 feasibility assessment

Measured 21 October 2026. **CONDITIONAL GO for the two analytical tasks**, provided
we accept a behavioral client funnel without actual sessions/checkout/order IDs,
retain the event-based purchase target, and resolve source-version/timezone and
NonCommercial-use requirements before adopting it. This is evidence to consider
replacement, not approval to migrate. Existing REES46 remains unchanged.

## Source, licensing and access

Used the **original** six-file Synerise archive linked by the
[official dataset page](https://recsys.synerise.com/data-set), without competition
client filtering or input/target preprocessing. The public download needed no
account. Downloaded 2,062,884,710 bytes; extracted Parquet totals
2,603,781,937 bytes. SHA-256: `e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7`.
[Inventory and per-file hashes](../../analysis/synerise/download-manifest.json).
The server reported last-modified 12 November 2025; download completed in about
75 seconds. No interrupted-transfer resume test was needed.

Attribution: Universal Behavioral Modeling Dataset © 2025 Synerise SA,
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), as identified by
[the organizer's notice](https://recsys.synerise.com/summary). Give credit, link the
license, and identify analytical transformations; do not imply endorsement.
Noncommercial portfolio publication must respect the NonCommercial restriction;
public GitHub visibility does not by itself establish compliant use. Commercial,
sponsored or paid reuse requires a separate permission assessment. The organizer's
code MIT license is distinct from its data license. Only aggregate results are
included here; source records remain ignored local files.

## Verified schemas and counts

| Event | Published | Measured | Difference | Exact clients | Excess duplicates |
| --- | --- | --- | --- | --- | --- |
| page_visit | 150,713,186 | 199,451,980 | 48,738,794 | 21,993,998 | 20,699,407 |
| search_query | 9,571,258 | 13,223,769 | 3,652,511 | 1,629,447 | 617,143 |
| add_to_cart | 5,235,882 | 7,541,117 | 2,305,235 | 2,333,463 | 161,493 |
| remove_from_cart | 1,697,891 | 2,688,894 | 991,003 | 694,391 | 153,588 |
| product_buy | 1,682,296 | 2,318,502 | 636,206 | 909,210 | 380,903 |

Total measured events: **225,224,262**. All five counts exceed the published
reference. These are complete scans, not estimates or sampled clients. The public
URL currently supplies a different-sized corpus than the reference table. A later
release or different filtering is plausible, but **the exact cause is unconfirmed**;
no rows were removed to force agreement. Confirm the release with the publisher
before claiming equivalence to published competition results. Hash-pinned results
remain reproducible for this actual archive.

See [full measured schema/null table](../../analysis/synerise/schema.md). Event
identifiers are BIGINT; timestamps are VARCHAR. Purchase/cart records have SKU;
page records have URL; searches have a VARCHAR query-vector encoding. Properties
have SKU, category, price, name, all nullable by schema. Every source column has
**zero observed nulls** and every event timestamp parses successfully. All parsed
times have whole-second precision. One page row has a nonpositive client ID; none
of the other event types do. We retain it and flag it, not infer its meaning.
Approximate distinct-client diagnostics are also recorded, but diverge noticeably
from exact counts; conclusions use exact values.

| Event | First timestamp | Last timestamp | Distinct SKU / URL |
| --- | --- | --- | --- |
| page_visit | 2022-06-23 00:10:00 | 2022-12-08 00:09:59 | 15,293,447 |
| search_query | 2022-06-23 00:10:00 | 2022-12-08 00:09:55 | not applicable |
| add_to_cart | 2022-06-23 00:10:20 | 2022-12-08 00:09:55 | 1,444,160 |
| remove_from_cart | 2022-06-23 00:12:25 | 2022-12-08 00:09:40 | 824,536 |
| product_buy | 2022-06-23 00:12:15 | 2022-12-08 00:09:15 | 639,126 |

No source timezone is established by the inspected documentation. All dates and
cutoffs in this report are **source-clock times**, not verified UTC. All five event
types have records on every one of the 169 calendar dates between
their endpoints; this does not prove uninterrupted within-day tracking. Ordering is
valid within the supplied clock, but exact UTC deployment alignment requires
confirmation. Approximately 96.7% of each event type's seconds are multiples of
five, so timestamp coarsening/ties are material. We do not invent subsecond order.

Exact duplicate rates are excess rows / raw rows, computed from all source columns;
raw multiplicities remain intact. Purchase excess duplicates are
380,903
(16.43%).
Page excess duplicates are 20,699,407
(10.38%).
They may reflect repeated signals, instrumentation or preprocessing; cause is unknown.

## Product properties and encoded fields

Properties contain 1,534,050 rows and 1,534,050 distinct SKUs,
with no duplicate SKU keys or exact duplicate rows; 6,912
categories and price buckets 0–99.
Every observed buy/add/remove SKU matches properties. Full property joins therefore
avoid unmatched records in this version; never assume this for another release.

All measured query/name vectors have 16 extracted integers, stored as
whitespace-separated strings. The dataset webpage describes 20-dimensional queries,
while the repository describes 16-code quantization: actual files support the
latter. They are not readable query text or ordinary continuous semantic vectors.
Price is an anonymized bucket, **not money or revenue**. Static properties have no
valid-from timestamp: historical feature availability is not verifiable without
an explicit immutability assumption or a temporal source. URL IDs have no supplied
SKU/page-type mapping; no product-detail views can be reconstructed defensibly.

## Persistent client identity and history

Exact observed clients overall: **22,298,361**. Clients active on multiple
days: 7,508,499; across multiple months:
5,122,620. Purchasing clients: 909,210;
clients purchasing on more than one date: 210,633.

Median / p90 events per client: 2.0 / 19.0;
maximum 55,639. Median / p90 active days:
1.0 / 4.0. Median / p90 first-to-last
observed span: 0.00 / 63.28 days.
Median recency from dataset end: 67.33 days.
These are observation spans, not account tenure or complete customer histories.

The same typed client IDs occur across event types; measured overlaps with purchase
clients are in `supplement.json`. This supports longitudinal joins. It does not
prove a person-level identity, logged-in status, cross-device completeness or
absence of identity resets. The large page population is much broader than the
purchaser cohort. No anonymous/logged-in distinction is supplied.

## Purchase interpretation and repeat signals

| Definition | Purchasers | Repeat purchasers | Median signals | Median gap days | Zero gaps |
| --- | --- | --- | --- | --- | --- |
| A_event | 909,210 | 457,006 | 2.0000 | 0.0000 | 898,001 |
| B_timestamp_occasion | 909,210 | 246,601 | 1.0000 | 9.4259 | 0 |
| C_purchase_day | 909,210 | 210,633 | 1.0000 | 17.0000 | 0 |


There are 1,420,501 distinct client/timestamp occasions;
473,600 have multiple rows and
232,499 contain multiple SKUs. Maximum rows at one occasion:
168. This is direct evidence that row frequency is not order
frequency. Same-time multi-SKU activity is compatible with basket transactions,
but **no order identifier exists**. Same-day and same-time grouping are sensitivity
heuristics, never reconstructed true orders.

A retains all item-level product_buy signals. B collapses exact customer/time;
C collapses customer/calendar date. Zero-day gaps in A include ties/duplicates.
B removes same-time multiplicity, and C removes same-day multiplicity. Positive
inter-signal gaps within one hour and p90 gaps are in the full results. Repeat
client/SKU and client/category pair counts are also measured there, requiring
more than one distinct purchase timestamp. Refund, cancellation, quantity and
completed-order status cannot be established from these columns.

| Month | Purchase events | Purchasing clients |
| --- | --- | --- |
| 2022-06-01 00:00:00 | 75,880 | 45,950 |
| 2022-07-01 00:00:00 | 357,933 | 196,357 |
| 2022-08-01 00:00:00 | 374,376 | 189,813 |
| 2022-09-01 00:00:00 | 382,762 | 192,182 |
| 2022-10-01 00:00:00 | 452,019 | 204,467 |
| 2022-11-01 00:00:00 | 529,373 | 232,296 |
| 2022-12-01 00:00:00 | 146,159 | 79,293 |


## Behavioral funnels

The business interpretation is observed page activity → cart action → purchase
signal, with **search optional**. Do not infer view_item, checkout, shipping,
payment or actual sessions. Full-period cumulative event presence:

| Presence stage | Clients |
| --- | --- |
| customers | 22,298,361 |
| page | 21,993,998 |
| page_cart | 2,295,307 |
| page_cart_buy | 573,331 |
| page_search | 1,624,918 |
| page_search_cart | 800,783 |
| page_search_cart_buy | 308,185 |
| purchasers_without_search | 589,284 |
| purchasers_without_cart | 327,532 |

Strictly chronological, bounded from initial page to conversion:

| Window | Page | Page→cart | Page→cart→buy | Page→search | →cart | →buy | Same-SKU cart→buy clients |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full history | 21,993,998 | 2,256,271 | 549,271 | 1,582,497 | 610,578 | 225,750 | 547,547 |
| 1 days | 21,993,998 | 2,242,294 | 530,232 | 1,571,077 | 519,568 | 173,697 | 534,727 |
| 7 days | 21,993,998 | 2,247,779 | 541,225 | 1,577,459 | 552,789 | 196,395 | 544,552 |
| 30 days | 21,993,998 | 2,252,228 | 545,387 | 1,580,796 | 584,975 | 212,802 | 547,045 |

All counts are unique clients per cumulative stage; repeat events cannot inflate
converted clients. Timestamps must strictly increase. A later valid chain can
qualify even if earlier records are out of order. The full-history chain is not
a session; 1/7/30-day alternatives constrain attribution. These limits are
exploratory, not an established business conversion window.

Same-SKU cart-to-buy counts are separate product-specific evidence, not a SKU
page funnel. Page/search cannot be assigned a product. Equal-time cross-event
pairs are measured in `supplement.json` and excluded as ordering evidence.
Missing cart/search records are not repaired from a purchase. Mandatory-search
funnels exclude legitimate nonsearch journeys and must not be the sole KPI.

For the 30-day no-search funnel, page→cart drop-off is
89.76%;
qualifying cart→purchase drop-off is
75.78%.
There is no natural session identifier. No inactivity-based session was generated.

## Chronological 14-day ML feasibility

| Snapshot (source clock) | Eligible | Positive | Negative | Rate | Label end |
| --- | --- | --- | --- | --- | --- |
| 2022-08-01 00:00:00 | 234,827 | 14,243 | 220,584 | 6.07% | 2022-08-15 00:00:00 |
| 2022-09-01 00:00:00 | 397,836 | 22,003 | 375,833 | 5.53% | 2022-09-15 00:00:00 |
| 2022-10-01 00:00:00 | 550,798 | 30,016 | 520,782 | 5.45% | 2022-10-15 00:00:00 |
| 2022-11-01 00:00:00 | 700,807 | 37,528 | 663,279 | 5.35% | 2022-11-15 00:00:00 |

Dates are derived from the measured range: four latest month starts at least two
month boundaries after the first month and with 14 days before the last event.
Use the first two for training, third for validation, fourth for untouched holdout.
Every eligible client has a purchase strictly before its cutoff; history uses
`timestamp < t`, and labels alone use `[t,t+14 days)`. Training labels end before
validation, and validation labels end before holdout. No features/models were built.

A, B and C have **identical binary eligibility and labels at these midnight
cutoffs**, verified automatically. Grouping at the same timestamp/day cannot move
a signal across these day-aligned boundaries. That agreement does not validate
order semantics; frequency features and repeat counts above differ substantially.

Observed history before these snapshots is approximately 39, 70, 100 and 131 days,
respectively; it is a maximum dataset lookback, not per-customer tenure.

Ever-purchaser cohorts are nested. Independent first-purchase queries confirmed
all six pairwise overlaps (stored in supplement.json). Shared-client counts equal the earlier
snapshot's eligible count; repeated clients are expected, not independent samples.
This is returning-customer evaluation, not new-customer generalization. Positive
rates vary by date; preserve chronological holdout and compare prevalence baselines
later. No model quality, feature importance or predictive lift is claimed.

History is left-censored at the source start; late outcomes are right-censored.
Observed bounds and daily continuity are necessary but cannot prove complete
logging. All daily/monthly event and unique-client aggregates are retained. Require
upstream timezone/coverage confirmation before treating negative labels as fully
observed business outcomes.

## Historical feature availability and sparsity

At 2022-11-01 00:00:00, 700,807 eligible prior purchasers:

| 30-day feature | Zero / missing activity clients | Fraction of eligible |
| --- | --- | --- |
| Any activity | 368,458 | 52.58% |
| Page visits | 421,749 | 60.18% |
| Searches | 592,943 | 84.61% |
| Cart additions | 538,640 | 76.86% |
| Cart removals | 622,471 | 88.82% |
| Purchases | 500,501 | 71.42% |


Maximum timestamp contributing to this historical coverage:
2022-10-31 23:59:55, strictly before cutoff. No future events or
competition target arrays enter it. Missing activity yields zeros rather than
customer exclusion. Median 30-day active days and distinct cart SKUs are both zero.

Recency, 7/30/60-day counts, active days, cart/remove/search/page frequencies,
SKU diversity, repeated SKU activity and recent/earlier activity ratios are
computable from cutoff-filtered raw events. Occasion/day frequency variants should
accompany event-frequency features. The first snapshot has only about 39 days of
observed history, so a 60-day
feature would be partial; use a common 30-day lookback or explicit coverage flags.
Category diversity and price-bucket preferences need an explicit assumption that
the undated static attributes were known at cutoff.
Historical cart-to-buy rates must count only purchases before cutoff, never use
future labels to finish historical carts. Trends need equal-length disjoint
historical windows and guarded zero denominators. Predictive usefulness remains
untested. No actual revenue/order-count feature is supported.

## Organizer target and temporal implementation

Inspected official repository revision
`e91c1a62f84611151a399ce157e6031a4a73618f`, including
[split_data.py](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/data_utils/split_data.py),
[target calculators](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/training_pipeline/target_calculators.py)
and
[task construction](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/training_pipeline/task_constructor.py).

The splitter uses a 14-day constant. Relative to final purchase time, it computes
training-target start as end minus 27 days, reset to midnight, then validation
start 14 days later. Input is strictly before training start; training target is
half-open up to validation start; validation includes the final endpoint. A
non-full final day means its last evaluation interval is not automatically 14 full
days. We use explicitly full half-open horizons instead.

Churn filtering loads externally supplied `active_clients.npy`; documentation
identifies these as relevant clients with prior purchases. The code itself does
not recompute that eligibility at each rolling cutoff. Churn is 1 for no target
purchase, inverse of our repeat-event target within the same universe/window.
Propensity is multilabel purchase presence for selected SKU/category/bucket values,
not unrestricted repeat purchasing. The splitter creates purchase-only targets,
so emptiness in the target calculator means no purchase there, not no activity.
No organizer training code was executed. Its full-file Pandas loading, fixed
selected client universe and embedding-model protocol are not reused. Reuse the
conceptual separation and cross-check label logic, not its whole benchmark.

## Resources and future compatibility

Preflight: about 1.4 TiB free disk and 128 GiB RAM. Archive + extracted Parquet
requires about 4.35 GiB; product properties are included. The page file alone is
2,010,901,793 bytes. It is much larger than the other event sources and dominates
client aggregation, duplicate grouping and temporal page joins.

DuckDB ran with 2 GB working memory, two threads and an 80 GB spill cap. The first
unpartitioned page-duplicate aggregation hit the cap and failed without changing
source data; a 32-way client partition strategy completed it. Customer histories
also use 32 partitions and funnels 16. This is important implementation evidence:
a naive whole-corpus groupby does not fit the project's existing budget. The cap
is a database working-memory setting, not a measured whole-process peak.
Per-query elapsed times and SQL are preserved; cached/resumed work is identified
by matching prior executed query text, so the final duration is not a clean
from-scratch end-to-end benchmark. CPU/IO caches and multiple local research
processes also affect timings. No ClickHouse load benchmark was performed.

For future storage, preserve five typed raw source tables and undated properties;
expose a normalized analytical UNION ALL with event kind, original client/time,
SKU where present, URL only for pages and quantized query only for searches.
Keep original timestamp text until timezone is resolved. A raw normalized projection
with three 8-byte identifiers/time fields is already about 5.4 GB uncompressed
before strings/vectors/null/provenance overhead. Actual compressed ClickHouse size
is **unmeasured**; reserve 10–20 GB as a planning allowance, plus temporary staging
and reconciliation space, rather than asserting a compression ratio.

At the earlier REES46 transfer sample of ~320k rows/s, a purely linear scale for
this corpus would be roughly 11.7 minutes of transfer.
That is an extrapolation, not a runtime promise: schema, sorting, disk, parsing and
reconciliation differ. Full pipeline runtime is unknown. Daily partitions and
bounded-memory batches would be practical investigation candidates after approval.
Do not use price buckets as Decimal revenue or force page URL into SKU. No database
migration, production schemas, dbt models or Docker operations were performed.

## Comparison and recommendation

REES46 has 20.69M validated events, five months, existing four customer snapshots
and measured baselines; its view event has SKU but no order ID. Synerise offers
much more real recorded activity, search/URL signals and substantially more
purchasing clients, but no documented product-page mapping or real sessions.
Both require item-event versus order caution. This corpus cannot support the full
GA4 checkout funnel, but it can support the requested meaningful behavioral funnel.

The synthetic generator had 303 purchasing login IDs, hand-written return behavior
and ~51–56% 14-day rates; it was useful for engineering, not real-customer model
validity. Synerise supplies measured real-world longitudinal purchase behavior,
with materially larger label cohorts. Public GA4 sample access remains a separate
INCONCLUSIVE assessment. Size alone is not the reason for this recommendation.

**CONDITIONAL GO:** retain raw multiplicity and event-target semantics; accept
purchase occasions as sensitivity heuristics, source-clock ordering until timezone
confirmation, optional search and missing checkout/session/page-type information;
pin the larger current release and resolve its count discrepancy; comply with
NonCommercial use and attribution. These restrictions permit research on both
required tasks. Do not call labels true repeat orders or claim customer identity
completeness. Review these conditions before replacing REES46. If exact order-level
outcomes or product-view/checkout stages are mandatory, this source does not meet
those stronger requirements.

## Reproducibility and outstanding limits

[Research instructions](../../analysis/synerise/README.md), source manifest, schema,
SELECT SQL, `run.py`, `supplement.py`, aggregate JSON and local boundary tests are
under `analysis/synerise/`. Raw archive/files are under ignored
`data/external/synerise/`. Query source SQL and hashes/timings are in `results.json`.
No client-level output is published. Exact duplicate and identity diagnostics,
all four snapshot definitions, 1/7/30-day funnels and historical coverage were
executed on the complete downloaded sources. No models were trained. Two local
tests passed for temporal boundaries, duplicate
occasion grouping, strict ordering, window bounds and same-SKU linkage; Ruff lint
and formatting passed. Automated report checks reconcile all A/B/C label counts,
full follow-up and strictly historical coverage.

Unresolved: publisher explanation of differing counts/dimensions, timestamp
timezone, actual orders/refunds/status, logging completeness, historical product
attribute availability, true identity completeness, compressed ClickHouse size,
full migration runtime and predictive quality. None is replaced by an invented
measurement. Source archive and extracted-file hashes were recorded; existing
REES46 artifacts, services and AIS were not opened for mutation. No commits/pushes.
