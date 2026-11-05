{{ config(tags=['customer_features_v4_historical']) }}
-- Fixed historical acceptance checks, separate from generic quality checks.
SELECT 1 FROM {{ ref('ml_customer_features') }}
HAVING count()!=547914 OR sum(target_30d)!=74781
 OR countIf(has_cart_activity_30d=1)!=325699
 OR countIf(has_cart_activity_30d=0 AND has_behavioral_activity_30d=1)!=48901
 OR countIf(has_behavioral_activity_30d=0)!=173314
 OR countIf(has_cart_activity_30d=1 AND target_30d=1)!=51784
 OR countIf(has_cart_activity_30d=0 AND has_behavioral_activity_30d=1 AND target_30d=1)!=6475
 OR countIf(has_behavioral_activity_30d=0 AND target_30d=1)!=16522
