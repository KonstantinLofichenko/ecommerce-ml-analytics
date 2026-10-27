{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['category_id', 'client_id']
    )
}}
SELECT c.client_id AS client_id, p.category_id AS category_id,
    min(parseDateTimeBestEffort(c.event_time_source)) AS first_cart_time
FROM {{ ref('stg_synerise_add_to_cart') }} c
INNER JOIN {{ ref('stg_synerise_product_properties') }} p ON c.sku=p.sku
GROUP BY category_id, client_id
