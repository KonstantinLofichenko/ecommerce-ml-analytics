{{ config(tags=['customer_features_v4']) }}
WITH expected AS ({{ customer_features_population() }})
SELECT coalesce(e.client_id,m.client_id) AS client_id
FROM expected e FULL OUTER JOIN {{ ref('ml_customer_features') }} m USING(client_id)
WHERE e.client_id IS NULL OR m.client_id IS NULL OR m.target_30d!=e.target_30d
 OR m.first_purchase_ts!=e.first_purchase_ts OR m.first_purchase_month!=e.first_purchase_month
SETTINGS join_use_nulls=1
