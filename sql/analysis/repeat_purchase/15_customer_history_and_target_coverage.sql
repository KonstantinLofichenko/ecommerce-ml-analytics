-- Final validated: Check eligible lookbacks, July–August customers and complete calendar target bounds.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:55:59.
SELECT count() customers,min(first_purchase_ts) first_anchor,max(first_purchase_ts) last_anchor,
 min(first_purchase_ts-INTERVAL 30 DAY) earliest_lookback,
 countIf(first_purchase_ts-INTERVAL 30 DAY<toDateTime('2022-06-23 00:12:25','UTC')) left_truncated,
 countIf(addDays(toDate(first_purchase_ts),31)>toDate('2022-12-08')) possibly_right_censored,
 countIf(first_purchase_ts<toDateTime('2022-08-23','UTC')) july23_aug22_customers,
 countIf(first_purchase_ts<toDateTime('2022-08-23','UTC') AND first_purchase_ts-INTERVAL 30 DAY<toDateTime('2022-06-23 00:12:25','UTC')) early_left_truncated,
 max(addDays(toDate(first_purchase_ts),30)) latest_target_date
  FROM synerise_analytics.ml_customer_features;
