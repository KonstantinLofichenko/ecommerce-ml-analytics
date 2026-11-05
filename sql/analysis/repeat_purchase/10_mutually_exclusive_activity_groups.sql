-- Final validated: Reconcile final cart-addition, other-behavior and no-behavior groups.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:43:48.
SELECT has_cart_activity_30d,has_behavioral_activity_30d,count() customers,sum(target_30d) repeat_customers
  FROM synerise_analytics.ml_customer_features
GROUP BY has_cart_activity_30d,has_behavioral_activity_30d
ORDER BY has_cart_activity_30d DESC,has_behavioral_activity_30d DESC;
