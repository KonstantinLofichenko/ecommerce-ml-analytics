-- Final validated: Reconcile fixed eligibility and later-date 1–30-day repeat positives.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:28:03.
SELECT count() n,countIf(days_to_second_purchase_date BETWEEN 1 AND 30) positives
  FROM synerise_analytics.int_synerise_customer_first_purchase f
 INNER JOIN synerise_analytics.fct_synerise_customer_repeat_purchase r
 USING(client_id)
 WHERE parseDateTimeBestEffort(f.first_purchase_at,'UTC') >= toDateTime('2022-07-23 00:12:25','UTC')
   AND parseDateTimeBestEffort(f.first_purchase_at,'UTC') < toDateTime('2022-11-08 00:00:00','UTC');
