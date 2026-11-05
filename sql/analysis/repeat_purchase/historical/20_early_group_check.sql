-- Historical diagnostic: Exact early group-check logic; earlier inconsistent results depended on the now-replaced table state.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:42:38.
-- Table identifier updated to the current name; current execution does NOT recreate the old state.
SELECT has_cart_activity_30d,has_behavioral_activity_30d,count() customers,sum(target_30d) positives
  FROM synerise_analytics.ml_customer_features
GROUP BY has_cart_activity_30d,has_behavioral_activity_30d
ORDER BY has_cart_activity_30d DESC,has_behavioral_activity_30d DESC;
