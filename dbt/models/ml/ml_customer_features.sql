{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id'],
        tags=['customer_features_v4']
    )
}}

WITH eligible AS (
    {{ customer_features_population() }}
)
SELECT p.client_id AS client_id,
    p.first_purchase_ts AS first_purchase_ts,
    p.first_purchase_month AS first_purchase_month,
    p.target_30d AS target_30d,
    coalesce(b.page_views_30d, toUInt64(0)) AS page_views_30d,
    coalesce(b.unique_pages_30d, toUInt64(0)) AS unique_pages_30d,
    coalesce(b.cart_adds_30d, toUInt64(0)) AS cart_adds_30d,
    coalesce(b.cart_removals_30d, toUInt64(0)) AS cart_removals_30d,
    coalesce(b.searches_30d, toUInt64(0)) AS searches_30d,
    coalesce(b.has_cart_activity_30d, toUInt8(0)) AS has_cart_activity_30d,
    coalesce(b.has_behavioral_activity_30d, toUInt8(0)) AS has_behavioral_activity_30d
FROM eligible AS p
LEFT JOIN {{ ref('int_customer_behavior_30d') }} AS b ON p.client_id = b.client_id
