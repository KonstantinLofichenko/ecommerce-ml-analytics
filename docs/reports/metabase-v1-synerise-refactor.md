# Synerise analytical layer — Metabase Dashboard V1.0

Completed **26 October 2026** using dbt-core 1.12.6, dbt-clickhouse 1.10.3 and
ClickHouse 25.8.33.6. All four canonical tables were rebuilt and validated.
**91 relevant dbt tests passed**, with no skips or warnings. Metabase was read only;
no cards, dashboards, connections or field metadata were edited.

Definitions and source limitations are centralized in the
[funnel data contract](../funnel-data-contract.md).

## Results and preservation

| Canonical table | Before rows | After rows | Unique business IDs | Build seconds |
| --- | ---: | ---: | ---: | ---: |
| dim_synerise_categories | 6,912 | 6,912 | 6,912 | 0.68 |
| dim_synerise_products | 1,534,050 | 1,534,050 | 1,534,050 | 2.16 |
| fct_synerise_funnel_by_category | 6,880 | 6,880 | 6,880 | 0.03 |
| fct_synerise_funnel_by_product | 1,444,160 | 1,444,160 | 1,444,160 | 4.45 |

The four-model invocation took **7.48 seconds**. The two narrow metric tables were
bootstrapped in a separate **0.39-second** invocation. Final tests took **4.82 seconds**.
These are observed local runs, not performance guarantees.

Before/after fingerprints over **every original output column** match for each
canonical model, the untouched overall funnel and the retained legacy dashboard
relation. Counts, UInt256 sums of tuple cityHash64 values, and XORs were compared.
They cover the original category paths, original SKU/category/price values, donor
ASIN/title assignments, provenance/quality flags and unrounded conversion rates.
Fingerprints are probabilistic evidence; mapping-formula, donor-membership,
source-coverage, and exact fact-to-intermediate grain comparisons supplement them.

| Funnel grain | Sum cart customers | Sum purchasing customers |
| --- | ---: | ---: |
| SKU | 5,791,963 | 1,182,574 |
| Original category | 4,335,239 | 995,059 |

These totals are sums **within their respective grains**, unchanged from the
preserved narrow metrics. Customers can appear in multiple rows. They are not
unique-customer totals and must not be equated to the overall funnel population.

All 17 protected raw/staging/legacy/overall relations retained their UUIDs and
metadata row counts. REES46 was independently counted at **20,692,840 rows**.
Raw Synerise and Amazon relations were not written. No event timestamps, ML code,
credentials, grants, Docker configuration, volumes or independent AIS resources
were modified. The overall funnel SQL and its three result rows are unchanged.
No commits or pushes were made.

Aggregate evidence, original-column baselines, table identities, build settings and
timings: [validation.json](../../analysis/catalog/metabase-v1/validation.json).
Detailed dbt invocation artifacts and initial failed-test evidence are retained
locally under ignored `data/processed/metabase-v1/`.

## Repository preparation validation

The later pre-commit check passed `dbt parse`, **91 dbt tests in 5.33 seconds**,
Ruff lint/format, and **74 Python tests**. Three opt-in live migration tests were
skipped by their existing default policy. Canonical original-column fingerprints,
the overall funnel, and all raw-source UUIDs/metadata counts still match the baseline.
REES46 still has **20,692,840 rows**. No dbt SQL, validated definitions, source data,
ML code, Metabase objects, credentials or service limits were changed by cleanup.

The legacy dashboard relation was already absent at this later check; this task
performed no DROP. The earlier baseline records its prior retained state.

This is the repository's first commit on `main`. Historical phase reports and
research evidence are retained because they contain unique decisions, failure
analysis or reproducibility details. The [report index](README.md) distinguishes
history from this single current dashboard acceptance report. Detailed hierarchy,
build commands, memory investigation, dependencies and manual Metabase SQL are
in [Dashboard V1.0 operations](../dashboard-v1-operations.md).

Git exclusions cover original datasets, Parquets/archives, local databases, virtual
environments, dbt output/packages/logs, root runtime logs, temporary exports and
private configuration. `.env.example` remains intentional. All commit candidates
were checked for configured credentials, private keys, binary content and files
at least 10 MB; none were found. The 2 MB timestamp/provenance JSON is intentional
research evidence. Existing Amazon source filenames/schema are documented with
an explicit limitation: no original immutable upstream checksum manifest is available.

## V2.0 validation checkpoint — 27 October 2026

Customer Time-to-Conversion is complete in the existing dashboard's second tab.
The four new models are `int_synerise_customer_first_cart`,
`int_synerise_customer_first_purchase_after_cart`,
`int_synerise_customer_conversion_times` and `fct_synerise_time_to_conversion`.
Definitions and populations are in the [V2 contract](../funnel-data-contract.md#customer-time-to-conversion--v20);
commands and memory history are in [operations](../dashboard-v1-operations.md#v20-build-and-test).

The reporting table was read and verified on 27 October 2026:

| Metric | Measured |
| --- | ---: |
| First-cart customers | 2,333,463 |
| Observed converters | 565,203 |
| Observed non-converters | 1,768,260 |
| P50 | 7.08 minutes |
| P75 | 102.42 stored minutes → 1.71 displayed hours |
| P90 | 18,234.93 stored minutes → 12.66 displayed days |
| Common seven-day-follow-up denominator | 2,208,140 |
| Converted within 1 hour / 24 hours / 7 days in that cohort | 391,873 / 436,456 / 470,986 |
| Stored cumulative fractions | 0.17747 / 0.19766 / 0.21330 |

Percentiles concern all observed converters; cumulative rates use the common mature
cohort. These are different populations. V2 has no page-visit requirement, unlike
V1's overall funnel. A prior independent read found zero V1 purchasing customers
absent from V2 converters; that subset check does not imply identical cohorts.

Parse passed. The final existing single-thread result artifact records **20 passing
tests**, no errors/skips/warnings, completed **06:24:09 Moscow time** (03:24:09 UTC),
with **0.61 seconds** suite elapsed. Inventory: 15 model/column checks plus five
singular tests, rather than the initially reported 15. Exact in-order uniqueness
checks avoid redundant generic uniqueness on conversion times. See operations for
the earlier global-memory startup failure and why it was not a duplicate-ID finding.

Current memory was verified at **17,179,869,184 bytes container (16 GiB)** and
**12,884,901,888 bytes server (12 GiB)** after the user's allocation change. Compose
validation passed. All original-column fingerprints for the two V1 dimensions and
three V1 facts still match the stored baseline. Protected REES46, Synerise and Amazon
raw-table UUIDs and metadata counts match that baseline, including REES46's
20,692,840 rows. No validated model SQL was refactored or raw tables rebuilt during
finalization. The allocation files are included as the user's reviewed configuration
changes. Metabase was not modified. Its cumulative-category refresh ordering remains
an accepted presentation limitation; timezone/censoring and historical full-refresh
resource limitations remain documented.

## V2.1 segment validation — 27 October 2026

Six new models were built sequentially, without rebuilding V1/V2, dimensions or
sources. Parse passed. **60/60 dbt tests passed in 7.98 seconds**: 40 new checks and
the existing 20 V2 customer tests. New checks cover composite uniqueness, null/flag
integrity, chronology/exact durations, first-cart population preservation, mature
cohorts, monotonic counts/rates, summary consistency, hierarchy validity and exact
V1 reconciliation. No correctness or memory failures occurred.

| Grain | Reporting rows | Cart memberships | Converted memberships | Seven-day eligible memberships |
| --- | ---: | ---: | ---: | ---: |
| Original category | 6,880 | 4,335,239 | 995,059 | 4,037,787 |
| SKU | 1,444,160 | 5,791,963 | 1,182,574 | 5,385,921 |

Cart and converter counts match V1 **at every category/SKU**, with zero differences.
Totals are memberships, not distinct people across grains. V2's existing customer
summary and both V1 reporting-table fingerprints match the pre-build baseline;
protected raw-table UUIDs and metadata counts are unchanged. Source files and
existing model SQL were not modified. Catalog mappings were reused, not regenerated.

Independent raw-event queries verified complete cohorts for categories **258, 791**
and SKUs **219232, 1243077**, including first qualifying purchases, cart/converter
counts, exact P50/P75/P90, mature denominators and all window numerators.
For example, category 258 has 102,796 cart memberships, 22,232 converters and
95,744 eligible memberships; P50/P75/P90 are 360/1,909/139,950 seconds.
SKU 219232 has 5,655 carts, 1,283 converters and 5,224 eligible memberships;
P50/P75/P90 are 1,710/72,654/528,045 seconds. These spot checks supplement the
whole-grain reconciliation and null-integrity tests, not complete value-level raw
reconciliation of every timestamp.

| New model | dbt build seconds | Logged INSERT peak bytes |
| --- | ---: | ---: |
| int_synerise_category_first_cart | 2.69 | 280,244,837 |
| int_synerise_product_first_cart | 1.36 | 87,359,414 |
| int_synerise_category_conversion_times | 2.38 | 394,719,881 |
| int_synerise_product_conversion_times | 2.39 | 361,858,533 |
| fct_synerise_time_to_conversion_by_category | 0.19 | 88,237,460 |
| fct_synerise_time_to_conversion_by_product | 6.39 | 454,778,603 |

Peak values are per-query ClickHouse tracker measurements, not continuous global
or container peaks. The three two-model invocations took 4.22, 4.87 and 6.69 seconds;
these exclude source spot checks, parse, tests and documentation. No memory limit
was increased; the existing 16 GiB container / 12 GiB server allocation was retained.
Generated logs and detailed temporary checks stay outside Git. Metabase SQL and
manual filter instructions are in the [operations guide](../dashboard-v1-operations.md#v21-category-and-product-segments).
No dashboard/tab was created or edited by the repository implementation. The
initial review did not commit or push; final publication is recorded below.

Censoring, unverified source-clock elapsed time, converter-only percentile selection,
small cohorts, synthetic display labels and the lack of true orders/sessions remain
limitations. No causality or statistical confidence claim is made from these metrics.

### Final V2.1 publication validation

On 27 October 2026 the user confirmed category/product Metabase integration and
formatting were complete in the existing Time to Conversion tab. Repository
finalization did not inspect or edit the dashboard. Reference questions and filter
configuration remain documented for reproduction.

Final `dbt parse` and **60/60 tests passed in 7.59 seconds** with one dbt thread.
Ruff, internal documentation links and whitespace checks passed. Existing V1
funnel/catalog fingerprints and V2 customer summary match their baselines;
protected REES46/Synerise/Amazon raw UUIDs and metadata counts are unchanged.

This checkpoint includes the successful subset of the user-requested SETTINGS
removal experiment: six models rebuilt with identical complete fingerprints.
Customer conversion retains required NULL-join semantics via dbt configuration.
The category conversion-history experiment exceeded the 1 GiB query limit, so its
original settings were restored and its existing table verified intact. Remaining
models retain their controls. See [operations](../dashboard-v1-operations.md#final-v21-settings-experiment-and-publication-checkpoint)
for the exact scope. No validated business definitions or memory limits changed.

## V2.2 cart non-conversion checkpoint — 27 October 2026

V2.2 reuses existing V2/V2.1 facts with no persistent model or matching change.
Parse and **62/62 tests passed in 8.28 seconds**, with one dbt thread: the existing
60 regressions plus two non-conversion partition/boundary tests. Four new native
question templates were executed, including rate and volume ranking modes at both
category and SKU grains. Both ranking modes returned 20 correctly ordered rows
with the default minimum eligible cohort of 100. Zero-denominator fixtures return
NULL shares; exact-window endpoints and seven-day eligibility boundaries passed.

| Overall first-cart cohort metric | Measured |
| --- | ---: |
| Seven-day eligible customers | 2,208,140 |
| Not converted within 1 hour | 1,816,267 / 82.25% |
| Not converted within 24 hours | 1,771,684 / 80.23% |
| Not converted within 7 days | 1,737,154 / 78.67% |
| Early share among seven-day converters | 83.20% |

The overall timing partition is **391,873 / 44,583 / 34,530 / 1,737,154**;
counts sum exactly to 2,208,140 and fractional shares sum to one within floating-point
tolerance. Category 258 independently matched **16,271 / 1,974 / 1,259 / 76,240**,
79.63% seven-day non-conversion and 83.42% early share. Category 4299 matched
1,036 eligible customers, 18 conversions and 98.26% seven-day non-conversion.
These are dated examples, not permanently pinned production benchmarks or claims
that either category is globally top-ranked.

Rates are stored in the delivered SQL as 0–1 fractions, per user choice; displayed
percentages above are presentation values. No extra factors of 100 are applied
by the queries. An initial distribution-query tuple/output alias collision was
corrected during query validation; the final four queries passed. No source or
established model logic changed.

At the initial 27 October handoff, dashboard deployment was **manual, not performed**:
no Metabase UI/API credentials
or deployment client are configured. The [setup package](../metabase/v22/README.md)
contains all questions, six KPI mappings, 100% timing distribution, two category
rankings, two SKU rankings and applicable hierarchy/SKU/cohort filters. No date
filter is offered on lifetime aggregates. Original source events are anonymized;
only the catalog associations/labels are synthetic. Existing data-quality,
censoring and statistical-selection limitations remain applicable.

Final preservation checks matched existing V1 category/SKU and V2 customer-summary
fingerprints, plus protected raw-table UUIDs/counts. Ruff lint/format, documentation
paths and whitespace checks passed. No prior dbt model or definition changed.
The V2.1 question files were concurrently relocated to `docs/metabase/v21/` without
content changes; their documentation links were updated, and the relocation was
preserved. At that initial handoff, no files were staged, committed or pushed for V2.2.

## V2.2 final dashboard validation — 28 October 2026

Read-only Metabase PostgreSQL metadata inspection confirmed deployment in the
existing **Synerise funnel analytics** dashboard (ID 2), on **Cart Abandonment**
(tab 6), alongside Funnel Analytics and Time to Conversion. This supersedes the
initial standalone-dashboard/manual-handoff proposal. No Metabase write, session
extraction, credential change or browser-rendered visual inspection was performed.

The deployed tab has a definition banner, six overall Number cards (51–56), a
four-outcome **pie** (57), and category/product **top-100 tables** (58–59).
Tables switch between rate and volume through **Rank by**, default `rate`; minimum
eligible cohort defaults to 100. Only the tables receive hierarchy, cohort-minimum
and rank mappings. Overall KPIs and the pie have no filter mappings. There are no
standalone category-ID/SKU/date controls. Rates/shares use Percentage formatting
with **one decimal**, not stored 0–100 values. Saved metadata uses equality for
level 1 and case-insensitive contains widgets for levels 2–4. The
[dashboard reference](../metabase/v22/README.md) records exact cards and mappings.

Reference SQL bodies match the four saved question bodies, ignoring comments and
whitespace. Both category and product ranking modes were executed with minimum
cohort 100 and returned 100 correctly ordered rows. Category 258/4299 examples and
the overall count/share partition passed again. Earlier top-20 and stacked-bar
references above describe the initial proposal, not the final deployed layout.

Final `dbt parse` passed and **62/62 tests passed in 8.02 seconds**, one dbt thread,
with zero skips/errors/warnings. Existing V1 category/SKU and V2 customer reporting
fingerprints, plus protected raw-table UUIDs/counts, match their pre-extension
baselines. Existing dbt model/ML/infrastructure code is unchanged; only two new
singular validation tests were added. No raw or analytical table rebuild was needed.
Ruff, whitespace and internal-link checks passed. The V2.1 query relocation is
preserved byte-for-byte and its references resolve. Runtime logs, generated dbt
artifacts and detailed dashboard metadata remain outside the commit.
