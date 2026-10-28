# Customer Retention — V3.0 Metabase queries

Read from dashboard 2, **Customer Retention** tab, and validated against ClickHouse
on 28 October 2026. Seven saved cards use four distinct queries. No dashboard,
saved question, dbt model or dataset was modified by this SQL recovery.

| Card ID / title | SQL | Visualization / result column |
| --- | --- | --- |
| 60 — Monthly Customer Retention | [Monthly retention](monthly-customer-retention.sql) | Pivot: rows `cohort_month`, columns `month_number`, value `sum` |
| 61 — Observed Repeat-Purchase Rate | [Shared repeat KPIs](repeat-purchase-kpis.sql) | Number: `observed_repeat_purchase_rate_pct`, Percentage, one decimal |
| 62 — Repeat Purchasers | Same shared repeat KPIs | Number: `repeat_purchasers`, integer |
| 63 — Median Days to Second Purchase | Same shared repeat KPIs | Number: `median_days_to_second_purchase`, suffix ` days` |
| 64 — 30-Day Repeat-Purchase Rate | Same shared repeat KPIs | Number: `repeat_purchase_rate_30d_pct`, Percentage, one decimal |
| 65 — 30-Day Repeat-Purchase Rate by Cohort | [30-day cohort rates](repeat-purchase-30d-by-cohort.sql) | Bar: time-series `cohort_month`, metric `repeat_purchase_rate_30d_pct`, Percentage, one decimal |
| 66 — Purchase Frequency Distribution | [Purchase frequency](purchase-frequency-distribution.sql) | Bar: ordinal `purchase_dates_group`, integer `customers` |

Cards 61–64 contain identical SQL; choose the indicated scalar field when
reproducing each question. No template variables or dashboard filter mappings
are present on these seven cards.

## Provenance and reproduction

The three native SQL files are **Recovered**, with one representation change:
the saved metadata contains literal backslash-n newline escapes in the SQL string.
Those escapes are converted to actual line breaks in the files. Calculations,
aliases and clauses are otherwise preserved; these are not byte-identical strings.

Card 60 is GUI/MBQL, so its SQL is **Reconstructed**, not recovered generated SQL.
It groups source table 41 (`fct_synerise_customer_monthly_retention`) by cohort date
(field 332, day granularity) and month offset (334), summing retention rate (337).
The fact has one row per cell, so this sum equals that cell's rate. Do not sum
across cohorts or offsets to obtain an overall retention rate.

For the exact saved pivot configuration, use the GUI source table, group by
`cohort_month` and `month_number`, and sum `retention_rate`. Metabase can restrict
pivot visualization for native SQL questions; the SQL file provides the equivalent
flat result, not a guarantee that a native question can directly render a pivot.
Hide row/column totals, format `sum` as Percentage with one decimal and title
“Retention Rate”; title the cohort column “Cohort Month”. The saved conditional
format rules, in order, are `<0.1` pink (`#F7C4C4`), `<0.5` blue (`#87BCEC`),
`<=1` green (`#A7D07C`). Field 337 supplies Percentage formatting on the GUI source;
apply it explicitly to a new native result. Rates remain **0–1 fractions**.
The cohort/frequency bars use blue (`#87BCEC`).

## Populations and limitations

See [V3 model definitions and coverage policy](../../customer-retention.md).
Monthly retention is non-cumulative activity relative to first observed purchase.
The fact excludes boundary cohort/outcome months and flags assumed continuous
interior-month coverage (`coverage_verified=0`). Empty future cells are unavailable,
not zero. The reconstructed pivot preserves the saved query, which does not expose
the coverage flag; retain the coverage warning in accompanying dashboard text.

Repeat KPIs and frequency use `fct_synerise_customer_repeat_purchase`, including
partial cohort months. Repeat means at least two **distinct purchase dates**, not
orders or two item-level event rows. Observed repeat rate and median second-date
gap use all observed history; the median is among observed repeat purchasers.
They remain affected by unequal follow-up and end-of-file censoring.

The recovered 30-day queries derive their endpoint from the maximum **purchase
date in the repeat summary**, not the all-event observation-window table. They
include customers whose first date is at most endpoint minus 30 days, and count
second-date gaps inclusively from 1 through 30. This is source-calendar-date
arithmetic, not verified 720-hour follow-up or certified continuous collection.
The all-event and purchase endpoint dates both currently equal 8 December 2022;
they need not remain equal with new data. Preserve this distinction when reviewing
future extensions. June's partial cohort is included here, and November includes
only customers with enough date-based follow-up; these populations differ from
the monthly retention pivot.

Rates use `nullIf` for zero denominators and are rounded to four decimal places;
`_pct` names do not imply 0–100 values. SQL uses the saved conditional quantile
behavior; an empty repeat population should not be presented as a measured median.
No arbitrary zero-frequency buckets are inserted by the frequency query. Source
clock/timezone is unverified. No synthetic Amazon labels are used by these cards.

## Read-only validation

All four SQL files executed successfully against current ClickHouse tables:

- Retention: 15 cells; July offsets 0–4 match rates 1, 0.112009, 0.093865,
  0.092838 and 0.095549 (display rounding only).
- Observed repeat rate: **0.2317**; repeat purchasers: **210,633**;
  median second-date gap: **24 days**; 30-day rate: **0.1404**.
- 30-day cohort rows: June–November, with eligible counts 45,950; 188,877;
  163,009; 152,962; 150,009; 38,412. November is a partially eligible cohort.
- Frequency counts for 1, 2, 3, 4, 5, 6+ dates: **698,577; 129,939;
  41,576; 17,404; 8,496; 13,218**. They sum to 909,210 customers;
  all groups after the first sum to 210,633 repeat purchasers.

Validation covers SELECT execution, saved source/field mappings and numerical
agreement. It does not claim screenshot equivalence or modify visual settings.
