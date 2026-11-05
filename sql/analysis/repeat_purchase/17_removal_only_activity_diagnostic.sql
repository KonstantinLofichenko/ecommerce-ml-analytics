-- Final validated: Distinguish additions from removal-only activity; explains the earlier cart-group discrepancy.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:42:38.
SELECT countIf(cart_adds_30d>0) adds_customers,countIf(cart_adds_30d=0 AND cart_removals_30d>0) removal_only_customers
  FROM synerise_analytics.ml_customer_features;
