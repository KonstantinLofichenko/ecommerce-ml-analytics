# Phase 2.3 — Customer-level snapshot features

Database: `data/processed/ecommerce.duckdb`. Analytical table: `customer_snapshot_features`. No models were trained.

Built **243,162 customer-snapshot rows** with exactly one row per `(prediction_date, user_id)`. All events and existing analytical tables are preserved. Only the feature table and its aggregate build audit are replaced.

## Row counts and label distribution

| prediction_date | eligible_customers | positive_labels | negative_labels | positive_rate |
| --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 25762 | 2456 | 23306 | 0.095334 |
| 2019-12-01 00:00:00 | 52523 | 3493 | 49030 | 0.066504 |
| 2020-01-01 00:00:00 | 72225 | 3831 | 68394 | 0.053043 |
| 2020-02-01 00:00:00 | 92652 | 4528 | 88124 | 0.048871 |

Positive rates are fractions. A row is eligible when a known customer has any timestamped purchase strictly before midnight UTC on the prediction date, including purchases with missing session IDs. `target_14d` is 1 for any raw purchase in [prediction_date, prediction_date + 14 days), else 0. Purchases are recorded events, not inferred orders or reconstructed session completions.

## Reconciliation with supplied Phase 2.1 results

| prediction_date | expected_eligible | expected_positive | eligible_difference | positive_difference | reconciliation |
| --- | --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 25762 | 2373 | 0 | 83 | DISCREPANCY: inspect source coverage and snapshot definitions |
| 2019-12-01 00:00:00 | 52523 | 3382 | 0 | 111 | DISCREPANCY: inspect source coverage and snapshot definitions |
| 2020-01-01 00:00:00 | 72225 | 3699 | 0 | 132 | DISCREPANCY: inspect source coverage and snapshot definitions |
| 2020-02-01 00:00:00 | 92652 | 4380 | 0 | 148 | DISCREPANCY: inspect source coverage and snapshot definitions |

Discrepancies or unavailable reference counts are shown explicitly above. Definitions have not been changed to force agreement. Compare input coverage, UTC boundaries, prior-purchase eligibility and null-ID handling before proceeding.

### Label-definition diagnostic

| prediction_date | event_target_positives | new_session_positives | event_only_positives | known_session_positives |
| --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 2456 | 2373 | 83 | 2456 |
| 2019-12-01 00:00:00 | 3493 | 3382 | 111 | 3493 |
| 2020-01-01 00:00:00 | 3831 | 3699 | 132 | 3831 |
| 2020-02-01 00:00:00 | 4528 | 4380 | 148 | 4528 |

`new_session_positives` counts eligible customers with a known customer/session pair whose **first observed purchase** falls in the future 14-day window. `event_only_positives` captures requested event-target positives without such a new purchasing session. This alternative is diagnostic only; it does not change `target_14d`. If event and known-session positives agree, missing session IDs do not explain the positive-count difference. All session-first timestamps in this diagnostic are recomputed from raw events and never enter features.

**Measured finding:** the alternative first-purchase-in-session definition reproduces every supplied positive count exactly. Additional event-target positives have future purchases in sessions already purchasing before the snapshot, without a new purchasing session in the window. Missing session IDs do not explain these differences. This supports a label-definition mismatch; the original Phase 2.1 SQL was not available for direct verification. The requested event-based target is preserved.

## Historical feature definitions

| feature | definition |
| --- | --- |
| days_since_last_purchase | Elapsed fractional UTC days since latest prior purchase. |
| purchase_sessions_30d | Distinct known customer/session pairs with a purchase in [t−30d, t). |
| sessions_30d | Distinct known customer/session pairs with any event in [t−30d, t). |
| view_events_30d | Raw view-event count in [t−30d, t). |
| cart_events_30d | Raw cart-event count in [t−30d, t). |
| remove_events_30d | Raw remove_from_cart-event count in [t−30d, t). |
| purchase_events_30d | Raw purchase-event count in [t−30d, t). |
| distinct_products_30d | Distinct nonmissing products across all events in [t−30d, t). |
| days_since_last_event | Elapsed fractional UTC days since latest prior event. |
| historical_purchasing_sessions | Distinct known purchasing customer/session pairs before t. |

Here t is midnight UTC on `prediction_date`. Every feature uses events strictly before t. The trailing window is [t − 30 × 24 hours, t); recency uses fractional elapsed 24-hour days. Historical means all observed data since October 2019, not the customer's lifetime. Future events are queried separately only for labels. Whole-session/customer summaries, deduplicated views, and source month fields do not feed the feature calculations.

Sessions use exact `(user_id, user_session)` STRUCT keys. Null session IDs never form a session, but their events still count toward eligibility, targets, recency, event totals and distinct products. Distinct products exclude null product IDs. A session straddling a snapshot contributes only its historical events. Its future purchase may set the target even if the same session also purchased before t: this is the requested future-purchase-event definition, not a separate-order label. Raw duplicates remain in event counts; distinct sessions/products are unaffected.

## Validation and temporal provenance

The feature table has a composite primary key, NOT NULL fields, binary-target and nonnegative-count checks. Independent raw SQL reconciles the complete sets of eligible and positive customer keys, not just their counts. Per-snapshot audits check prior purchases, historical/30-day bounds and label-window bounds. Synthetic tests additionally perturb future events to verify historical-feature invariance, and check both inclusive and exclusive boundaries. Zero error counts are required before committing. Reference-count mismatches are reported, not hidden.

| prediction_date | eligibility_key_errors | label_key_errors | duplicate_key_errors | feature_time_errors | prior_purchase_errors | label_time_errors |
| --- | --- | --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2019-12-01 00:00:00 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2020-01-01 00:00:00 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2020-02-01 00:00:00 | 0 | 0 | 0 | 0 | 0 | 0 |

### Observed contributor bounds

| prediction_date | latest_feature_event_utc | earliest_30d_event_utc | first_label_purchase_utc | last_label_purchase_utc | historical_events_missing_session |
| --- | --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 2019-10-31 23:59:36 | 2019-10-02 00:00:33 | 2019-11-01 01:51:14 | 2019-11-14 23:27:29 | 96 |
| 2019-12-01 00:00:00 | 2019-11-30 23:59:22 | 2019-11-01 00:00:02 | 2019-12-01 00:17:50 | 2019-12-14 23:25:06 | 359 |
| 2020-01-01 00:00:00 | 2019-12-31 23:58:55 | 2019-12-02 00:00:24 | 2020-01-01 00:52:11 | 2020-01-14 23:37:08 | 594 |
| 2020-02-01 00:00:00 | 2020-01-31 23:59:26 | 2020-01-02 00:00:00 | 2020-02-01 00:08:22 | 2020-02-14 23:55:38 | 1,076 |

## Null checks

| column_name | nulls |
| --- | --- |
| prediction_date | 0 |
| user_id | 0 |
| target_14d | 0 |
| days_since_last_purchase | 0 |
| purchase_sessions_30d | 0 |
| sessions_30d | 0 |
| view_events_30d | 0 |
| cart_events_30d | 0 |
| remove_events_30d | 0 |
| purchase_events_30d | 0 |
| distinct_products_30d | 0 |
| days_since_last_event | 0 |
| historical_purchasing_sessions | 0 |

All eligible customers have a timestamped prior purchase, so both recencies are defined. Count features are zero when there is no matching trailing activity. No missing recencies are imputed.

## Basic feature statistics

### 2019-11-01

| feature | rows | nulls | minimum | mean | median | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| days_since_last_purchase | 25762 | 0 | 0.003067 | 15.110929 | 15.144439 | 29.445413 | 30.992708 |
| purchase_sessions_30d | 25762 | 0 | 0 | 1.099177 | 1 | 2 | 31 |
| sessions_30d | 25762 | 0 | 0 | 7.540874 | 3 | 26 | 1,347 |
| view_events_30d | 25762 | 0 | 0 | 23.870235 | 9 | 92 | 1,808 |
| cart_events_30d | 25762 | 0 | 0 | 20.419028 | 11 | 70 | 1,047 |
| remove_events_30d | 25762 | 0 | 0 | 15.381104 | 4 | 62 | 1,861 |
| purchase_events_30d | 25762 | 0 | 0 | 9.205341 | 6 | 29 | 329 |
| distinct_products_30d | 25762 | 0 | 0 | 29.201537 | 16 | 99 | 1,104 |
| days_since_last_event | 25762 | 0 | 0.000278 | 12.092383 | 10.448362 | 28.480323 | 30.991088 |
| historical_purchasing_sessions | 25762 | 0 | 1 | 1.138343 | 1 | 2 | 31 |

### 2019-12-01

| feature | rows | nulls | minimum | mean | median | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| days_since_last_purchase | 52523 | 0 | 0.024375 | 25.824115 | 23.305856 | 57.343432 | 60.992708 |
| purchase_sessions_30d | 52523 | 0 | 0 | 0.696228 | 1 | 2 | 23 |
| sessions_30d | 52523 | 0 | 0 | 5.658664 | 2 | 21 | 2,030 |
| view_events_30d | 52523 | 0 | 0 | 17.176532 | 4 | 75 | 2,272 |
| cart_events_30d | 52523 | 0 | 0 | 14.583935 | 5 | 61 | 1,458 |
| remove_events_30d | 52523 | 0 | 0 | 11.094225 | 1 | 51 | 2,480 |
| purchase_events_30d | 52523 | 0 | 0 | 6.138587 | 2 | 25 | 438 |
| distinct_products_30d | 52523 | 0 | 0 | 20.822973 | 7 | 84 | 1,582 |
| days_since_last_event | 52523 | 0 | 0.000440 | 20.457087 | 15.261678 | 54.549204 | 60.991088 |
| historical_purchasing_sessions | 52523 | 0 | 1 | 1.250938 | 1 | 2 | 54 |

### 2020-01-01

| feature | rows | nulls | minimum | mean | median | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| days_since_last_purchase | 72225 | 0 | 0.001910 | 42.828393 | 39.465880 | 86.153667 | 91.992708 |
| purchase_sessions_30d | 72225 | 0 | 0 | 0.388619 | 0 | 1 | 31 |
| sessions_30d | 72225 | 0 | 0 | 3.086964 | 0 | 12 | 1,664 |
| view_events_30d | 72225 | 0 | 0 | 9.100948 | 0 | 44 | 1,832 |
| cart_events_30d | 72225 | 0 | 0 | 7.064438 | 0 | 34 | 1,336 |
| remove_events_30d | 72225 | 0 | 0 | 5.458290 | 0 | 27 | 2,309 |
| purchase_events_30d | 72225 | 0 | 0 | 2.851367 | 0 | 14 | 399 |
| distinct_products_30d | 72225 | 0 | 0 | 10.721925 | 0 | 51 | 1,420 |
| days_since_last_event | 72225 | 0 | 0.000752 | 34.712489 | 30.451134 | 83.183708 | 91.991088 |
| historical_purchasing_sessions | 72225 | 0 | 1 | 1.306888 | 1 | 3 | 85 |

### 2020-02-01

| feature | rows | nulls | minimum | mean | median | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| days_since_last_purchase | 92652 | 0 | 0.001088 | 56.241401 | 56.719803 | 115.376408 | 122.992708 |
| purchase_sessions_30d | 92652 | 0 | 0 | 0.344806 | 0 | 1 | 18 |
| sessions_30d | 92652 | 0 | 0 | 2.952003 | 0 | 12 | 1,864 |
| view_events_30d | 92652 | 0 | 0 | 8.841644 | 0 | 44 | 2,041 |
| cart_events_30d | 92652 | 0 | 0 | 7.072767 | 0 | 36 | 1,134 |
| remove_events_30d | 92652 | 0 | 0 | 5.435673 | 0 | 28 | 1,178 |
| purchase_events_30d | 92652 | 0 | 0 | 2.811898 | 0 | 15 | 263 |
| distinct_products_30d | 92652 | 0 | 0 | 10.562039 | 0 | 54 | 1,468 |
| days_since_last_event | 92652 | 0 | 0.000394 | 45.142134 | 40.620243 | 110.528861 | 122.991088 |
| historical_purchasing_sessions | 92652 | 0 | 1 | 1.365356 | 1 | 3 | 103 |

## Source quality and limitations

| raw_events | first_event_utc | last_event_utc | events_missing_customer | events_missing_timestamp | events_missing_session |
| --- | --- | --- | --- | --- | --- |
| 20692840 | 2019-10-01 00:00:00 | 2020-02-29 23:59:59 | 0 | 0 | 4598 |

Events with null customer IDs cannot be attributed and are excluded from snapshots. Untimestamped events cannot establish eligibility, feature windows or labels and are excluded from those calculations; raw source rows remain untouched. Null session events are excluded only from session counts. Aggregate quality counts above refer to the full source; audit null-session counts refer to eligible historical events per snapshot, so the same event may contribute at multiple dates.

A build requires the last observed event to reach each target window's exclusive end. This is a coverage guard, not proof of continuous logging or customer follow-up. The monthly source is assumed complete between its bounds; unseen purchases are observed negatives, not proof of no real-world purchase. History is left-censored at the first source event and January/February customers have more observed history than November customers. Snapshots repeat customers and overlap historical activity; later modeling must use temporal validation and avoid treating rows as independent. Session-ID reuse, duplicate provenance and missing product metadata remain upstream limitations. No deduplication policy or model split is selected here.

## Rebuild and inspect

```bash
source .venv/bin/activate
python scripts/build_customer_features.py
pytest
ruff check .
ruff format --check .
```

Optional `--prediction-date YYYY-MM-DD` arguments replace the default snapshot set. `--database`, `--report`, and `--output` select existing database and output paths. Rebuilds replace only the feature and audit tables inside one transaction; failures restore the prior feature dataset. Do not keep the database open in DBeaver while building. The existing 2 GB/two-thread DuckDB configuration and temporary spill directory are reused. Only aggregate results enter Pandas or exported CSV files.

```python
import duckdb

with duckdb.connect("data/processed/ecommerce.duckdb", read_only=True) as con:
    print(
        con.sql(
            "SELECT prediction_date, count(*), sum(target_14d) "
            "FROM customer_snapshot_features GROUP BY 1 ORDER BY 1"
        )
    )
    print(con.sql("SELECT * FROM customer_snapshot_features LIMIT 5"))
```
