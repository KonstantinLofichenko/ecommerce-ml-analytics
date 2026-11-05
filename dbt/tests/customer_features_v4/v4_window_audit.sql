{{ config(tags=['customer_features_v4']) }}
WITH eligible AS ({{ customer_features_population() }})
SELECT b.client_id FROM {{ ref('int_customer_behavior_30d') }} b
LEFT JOIN eligible p USING(client_id)
WHERE p.client_id IS NULL
 OR b.first_behavior_ts<p.first_purchase_ts-INTERVAL 30 DAY
 OR b.last_behavior_ts>=p.first_purchase_ts OR b.first_behavior_ts>b.last_behavior_ts
SETTINGS join_use_nulls=1
