-- Final validated: Count late first-purchase customers without observed positive outcomes using NULL-safe logic.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:58:06.
SELECT countIf(first_purchase_date>=toDate('2022-11-08') AND coalesce(days_to_second_purchase_date BETWEEN 1 AND 30,false)=0) AS late_unknown_negatives
  FROM synerise_analytics.fct_synerise_customer_repeat_purchase;
