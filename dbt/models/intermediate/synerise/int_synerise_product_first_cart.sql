{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['sku', 'client_id']
    )
}}
SELECT c.client_id AS client_id, c.sku AS sku,
    min(parseDateTimeBestEffort(c.event_time_source)) AS first_cart_time
FROM {{ ref('stg_synerise_add_to_cart') }} c
GROUP BY sku, client_id
