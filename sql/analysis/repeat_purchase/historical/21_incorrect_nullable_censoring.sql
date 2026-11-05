-- Known incorrect: Earlier censoring query incorrectly excluded NULL second-purchase gaps.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:55:59.
-- NOT(NULL BETWEEN 1 AND 30) remains NULL. Use 16 for the corrected negative/unknown count.
SELECT countIf(first_purchase_date>=toDate('2022-11-08')) late_first_purchase_customers,
 countIf(first_purchase_date>=toDate('2022-11-08') AND NOT (days_to_second_purchase_date BETWEEN 1 AND 30)) late_without_observed_positive,
 countIf(first_purchase_date>=toDate('2022-11-08') AND (days_to_second_purchase_date BETWEEN 1 AND 30)) late_observed_positives
  FROM synerise_analytics.fct_synerise_customer_repeat_purchase;
