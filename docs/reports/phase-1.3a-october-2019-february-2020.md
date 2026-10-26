# Phase 1.3A — Unified October 2019–February 2020 dataset

Database: `data/processed/ecommerce.duckdb`. All five local CSVs were loaded without deduplication.

## Row counts and duplicate comparison

Raw duplicate percentage = (raw rows − exact comparison rows) / raw rows × 100. Comparison duplicate percentage is zero by construction: the view groups every original source column, including missing values. Added provenance/parsed-time columns are not part of exact-row identity. Duplicate groups spanning files are assigned the earliest source month in the comparison only; raw provenance is unchanged. Thus monthly removal counts include cross-file duplicate attribution, not just within-file duplication. No permanent deduplication policy is selected.

### Overview

| raw_rows | comparison_rows | sessions | known_customers | first_event_utc | last_event_utc |
| --- | --- | --- | --- | --- | --- |
| 20692840 | 19583742 | 4536272 | 1639358 | 2019-10-01 00:00:00 | 2020-02-29 23:59:59 |

### Monthly counts

| month | raw_rows | comparison_rows | excess_duplicate_rows | raw_duplicate_percentage | comparison_duplicate_percentage |
| --- | --- | --- | --- | --- | --- |
| 2019-10 | 4102283 | 3889128 | 213155 | 5.196009 | 0 |
| 2019-11 | 4635837 | 4389144 | 246693 | 5.321434 | 0 |
| 2019-12 | 3533286 | 3349426 | 183860 | 5.203655 | 0 |
| 2020-01 | 4264752 | 4039652 | 225100 | 5.278150 | 0 |
| 2020-02 | 4156682 | 3916392 | 240290 | 5.780813 | 0 |

### Event type counts

| event_type | raw_rows | comparison_rows | excess_duplicate_rows | raw_duplicate_percentage | comparison_duplicate_percentage |
| --- | --- | --- | --- | --- | --- |
| cart | 5768333 | 5652991 | 115342 | 1.999572 | 0 |
| purchase | 1287007 | 1286102 | 905 | 0.070318 | 0 |
| remove_from_cart | 3979679 | 2987859 | 991820 | 24.922111 | 0 |
| view | 9657821 | 9656790 | 1031 | 0.010675 | 0 |

### Monthly event types

| month | event_type | raw_rows | comparison_rows | excess_duplicate_rows | raw_duplicate_percentage | comparison_duplicate_percentage |
| --- | --- | --- | --- | --- | --- | --- |
| 2019-10 | cart | 1232385 | 1204218 | 28167 | 2.285568 | 0 |
| 2019-10 | purchase | 245624 | 245281 | 343 | 0.139644 | 0 |
| 2019-10 | remove_from_cart | 762110 | 577579 | 184531 | 24.213171 | 0 |
| 2019-10 | view | 1862164 | 1862050 | 114 | 0.006122 | 0 |
| 2019-11 | cart | 1311807 | 1289632 | 22175 | 1.690416 | 0 |
| 2019-11 | purchase | 322417 | 322269 | 148 | 0.045903 | 0 |
| 2019-11 | remove_from_cart | 925481 | 701250 | 224231 | 24.228590 | 0 |
| 2019-11 | view | 2076132 | 2075993 | 139 | 0.006695 | 0 |
| 2019-12 | cart | 927124 | 911641 | 15483 | 1.670003 | 0 |
| 2019-12 | purchase | 213176 | 213066 | 110 | 0.051601 | 0 |
| 2019-12 | remove_from_cart | 664655 | 496498 | 168157 | 25.299892 | 0 |
| 2019-12 | view | 1728331 | 1728221 | 110 | 0.006365 | 0 |
| 2020-01 | cart | 1148323 | 1128662 | 19661 | 1.712149 | 0 |
| 2020-01 | purchase | 263797 | 263605 | 192 | 0.072783 | 0 |
| 2020-01 | remove_from_cart | 815024 | 609884 | 205140 | 25.169811 | 0 |
| 2020-01 | view | 2037608 | 2037501 | 107 | 0.005251 | 0 |
| 2020-02 | cart | 1148694 | 1118838 | 29856 | 2.599126 | 0 |
| 2020-02 | purchase | 241993 | 241881 | 112 | 0.046282 | 0 |
| 2020-02 | remove_from_cart | 812409 | 602648 | 209761 | 25.819630 | 0 |
| 2020-02 | view | 1953586 | 1953025 | 561 | 0.028716 | 0 |

### Quality by month

| month | raw_rows | excluded_session_events | excluded_customer_events | missing_timestamps | timestamp_source_month_mismatches |
| --- | --- | --- | --- | --- | --- |
| 2019-10 | 4102283 | 637 | 0 | 0 | 0 |
| 2019-11 | 4635837 | 813 | 0 | 0 | 0 |
| 2019-12 | 3533286 | 779 | 0 | 0 | 0 |
| 2020-01 | 4264752 | 1314 | 0 | 0 | 0 |
| 2020-02 | 4156682 | 1055 | 0 | 0 | 0 |

### Session quality

| metric | value |
| --- | --- |
| crossing_utc_days | 58023 |
| crossing_utc_months | 14228 |
| spanning_source_files | 14228 |
| sessions_with_unknown_customer | 0 |
| presence_complete | 106517 |
| chronological_complete | 100909 |
| tie_dependent_complete | 30 |

## Definitions and exclusions

- `raw_events`: original parsed strings plus source `month` (YYYY-MM) and `event_time_utc` (UTC TIMESTAMP). Empty fields remain NULL; literal NULL or whitespace strings retain the Phase 1.1 convention. All rows are retained. Malformed nonempty timestamps or inconsistent column schemas stop and roll back the build. Missing times and source-month mismatches are retained and reported.
- `events_exact_deduplicated`: exact-row comparison view only, evaluated over original columns. It does not feed session/customer tables.
- `session_summary` / `sessions`: one row per exact `(user_id, user_session)` pair, represented by a collision-free STRUCT key. Missing session IDs are excluded here only; unknown customer IDs remain as explicit NULL-user groups. Start/end and duration use observed UTC times, not active engagement time. Missing times do not establish order.
- Sessions are aggregated across all files, not split at midnight or month end. `source_months` counts input months; `calendar_months` counts observed UTC months. No inactivity timeout is inferred. Reuse of the same pair over a long period therefore yields one observed session; long sessions need future investigation.
- Session funnel flags reuse Phase 1.2 logic, across products. Presence needs event sets regardless of order; chronological progression requires strictly increasing view → cart → purchase times. Equal-time sequences cannot prove order; `tie_dependent_complete` reports additional non-strict completions.
- `customer_summary` / `customers`: known customers only, including their events with missing session IDs. First/last times are observed UTC bounds, not lifetime history. Total purchasing sessions count distinct known session IDs per customer, including purchases with missing timestamps.
- `customer_monthly_summary` and the five wide monthly count columns use event UTC month, not source-file month. A purchasing session is counted in each month where it records a purchase; summing monthly counts can exceed the distinct-period total. `sessions_first_purchased_in_month` instead assigns a session once, to its first timestamped purchase month. Missing session IDs cannot count as purchasing sessions; untimestamped purchases cannot be assigned to a calendar month and are reported in customer-summary quality columns. Monthly rows exist only for customer-months with timestamped activity; absent wide counts are zero, not proof of complete observation.
- Dataset boundaries censor earlier history and later behavior; missing recorded events do not establish behavioral absence. Purchase events are not order IDs. All primary summaries use raw records, so duplicate events inflate event counts. Category/brand missing values remain intact. No labels or models are created.

## Reproduction and querying

```bash
source .venv/bin/activate
python scripts/build_dataset.py
pytest
ruff check .
ruff format --check .
```

Options: `--raw-dir`, `--database`, `--report`, `--output`. Rebuilding replaces only the project's named tables/views in the default `main` schema inside one transaction. A failed build rolls back to the prior dataset; unrelated objects are retained. The single database file lives under ignored `data/processed/`. Report CSVs are aggregates and ignored by Git. Source files are read-only. DuckDB uses 2 GB working memory, two threads, and temporary spill space. Reserve several GB of free disk. Only aggregates enter Pandas.

```python
import duckdb

with duckdb.connect("data/processed/ecommerce.duckdb", read_only=True) as con:
    print(con.sql("SELECT month, count(*) FROM raw_events GROUP BY month ORDER BY month"))
    print(con.sql("SELECT * FROM sessions LIMIT 5"))
```

UTC timestamps are stored as TIMESTAMP values already normalized to UTC, so downstream queries need not depend on a connection's local timezone.

## Input manifest

SHA-256 fingerprints, byte sizes and row counts identify the exact local sources. Builds use existing CSVs only; no downloads are performed.

| month | filename | bytes | sha256 | rows |
| --- | --- | --- | --- | --- |
| 2019-10 | 2019-Oct.csv | 482542278 | d87b1124a003151592e722996c6295aba2d286626c5db624c49d749877478c23 | 4102283 |
| 2019-11 | 2019-Nov.csv | 545839412 | 25b03eea9020a64f97659a4cbce9d801ca81872910ce72348bfa607817539755 | 4635837 |
| 2019-12 | 2019-Dec.csv | 415302972 | ebf98f504e238109efa406d26a26a90e0d467faa938bf96b68e3fea663d2008e | 3533286 |
| 2020-01 | 2020-Jan.csv | 501792804 | c6d8d6bdcf0b6bccb61a14447afdca08e95683f34f279befb1ac580ddc214853 | 4264752 |
| 2020-02 | 2020-Feb.csv | 488799986 | 605c76fd75b01b9b60d1ae5f412d2a774158fdd18e0a95377b3c547a556f1c1b | 4156682 |
