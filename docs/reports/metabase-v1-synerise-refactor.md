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
