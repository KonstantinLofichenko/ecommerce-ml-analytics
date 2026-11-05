-- Final validated: Validate final population, uniqueness, NULLs, counts and activity-flag consistency.
-- Recovered from: ClickHouse query_log, 2026-10-30 01:54:37.
SELECT count() customers,uniqExact(client_id) unique_customers,sum(target_30d) positives,
countIf(target_30d NOT IN (0,1) OR has_cart_activity_30d NOT IN (0,1) OR has_behavioral_activity_30d NOT IN (0,1)
 OR page_views_30d<0 OR unique_pages_30d<0 OR cart_adds_30d<0 OR cart_removals_30d<0 OR searches_30d<0
 OR unique_pages_30d>page_views_30d OR has_cart_activity_30d!=(cart_adds_30d>0)
 OR has_behavioral_activity_30d!=(page_views_30d+cart_adds_30d+cart_removals_30d+searches_30d>0)) invalid_rows,
countIf(isNull(client_id) OR isNull(target_30d) OR isNull(first_purchase_ts) OR isNull(page_views_30d) OR isNull(unique_pages_30d)
 OR isNull(cart_adds_30d) OR isNull(cart_removals_30d) OR isNull(searches_30d) OR isNull(has_cart_activity_30d) OR isNull(has_behavioral_activity_30d)) null_rows
  FROM synerise_analytics.ml_customer_features;
