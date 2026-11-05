-- Final validated: Inspect approved chronological populations, excluded gaps and calendar label-availability dates.
-- Recovered from: ClickHouse query_log, 2026-10-30 01:54:38.
SELECT multiIf(first_purchase_ts<toDateTime('2022-08-16','UTC'),'proposed_revised_train',
 first_purchase_ts>=toDateTime('2022-09-15','UTC') AND first_purchase_ts<toDateTime('2022-10-01','UTC'),'proposed_revised_validation',
 first_purchase_ts>=toDateTime('2022-11-01','UTC'),'proposed_revised_test','purged_gap') split,
count() customers,min(first_purchase_ts) first_anchor,max(first_purchase_ts) last_anchor,
max(addDays(toDate(first_purchase_ts),31)) last_label_available_date
  FROM synerise_analytics.ml_customer_features
GROUP BY split
ORDER BY split;
