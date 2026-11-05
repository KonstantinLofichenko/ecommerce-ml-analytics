-- Final validated: Return zero rows only if all fixed historical population/group benchmarks match.
-- Recovered from: compiled dbt test v4_historical_benchmarks.sql.
-- Fixed historical acceptance checks, separate from generic quality checks.
SELECT 1
  FROM `synerise_analytics`.`ml_customer_features`
 HAVING count()!=547914
    OR sum(target_30d)!=74781
    OR countIf(has_cart_activity_30d=1)!=325699
    OR countIf(has_cart_activity_30d=0 AND has_behavioral_activity_30d=1)!=48901
    OR countIf(has_behavioral_activity_30d=0)!=173314
    OR countIf(has_cart_activity_30d=1 AND target_30d=1)!=51784
    OR countIf(has_cart_activity_30d=0 AND has_behavioral_activity_30d=1 AND target_30d=1)!=6475
    OR countIf(has_behavioral_activity_30d=0 AND target_30d=1)!=16522;
