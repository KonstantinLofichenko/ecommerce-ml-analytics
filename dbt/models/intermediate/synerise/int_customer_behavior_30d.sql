{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id'],
        tags=['customer_features_v4'],
        query_settings={
            'join_algorithm': 'grace_hash',
            'grace_hash_join_initial_buckets': 16
        }
    )
}}

WITH eligible AS (
    {{ customer_features_population() }}
), events AS (
    {{ customer_features_events() }}
)
SELECT e.client_id AS client_id,
    countIf(e.event_type = 'page_visit') AS page_views_30d,
    uniqExactIf(e.page_id, e.event_type = 'page_visit') AS unique_pages_30d,
    countIf(e.event_type = 'add_to_cart') AS cart_adds_30d,
    countIf(e.event_type = 'remove_from_cart') AS cart_removals_30d,
    countIf(e.event_type = 'search_query') AS searches_30d,
    toUInt8(cart_adds_30d > 0) AS has_cart_activity_30d,
    toUInt8(count() > 0) AS has_behavioral_activity_30d,
    -- Audit-only columns, not predictive inputs.
    min(e.event_ts) AS first_behavior_ts,
    max(e.event_ts) AS last_behavior_ts
FROM events AS e
INNER JOIN eligible AS p ON e.client_id = p.client_id
WHERE e.event_ts >= p.first_purchase_ts - INTERVAL 30 DAY
  AND e.event_ts < p.first_purchase_ts
GROUP BY e.client_id
