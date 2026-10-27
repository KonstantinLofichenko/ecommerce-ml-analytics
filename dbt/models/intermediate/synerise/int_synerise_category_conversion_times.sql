{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['category_id', 'client_id']
    )
}}
WITH qualifying_purchase AS (
    SELECT b.client_id AS client_id, c.category_id AS category_id,
        min(parseDateTimeBestEffort(b.event_time_source)) AS first_purchase_time
    FROM {{ ref('stg_synerise_product_buy') }} b
INNER JOIN {{ ref('stg_synerise_product_properties') }} p ON b.sku=p.sku
    INNER JOIN {{ ref('int_synerise_category_first_cart') }} c
        ON b.client_id=c.client_id AND p.category_id=c.category_id
    WHERE parseDateTimeBestEffort(b.event_time_source) >= c.first_cart_time
    GROUP BY category_id, client_id
)
SELECT c.client_id AS client_id, c.category_id AS category_id,
    c.first_cart_time AS first_cart_time, p.first_purchase_time AS first_purchase_time,
    toUInt8(isNotNull(p.first_purchase_time)) AS converted,
    if(isNotNull(p.first_purchase_time), dateDiff('second', c.first_cart_time, p.first_purchase_time), NULL)
        AS seconds_to_conversion
FROM {{ ref('int_synerise_category_first_cart') }} c
LEFT JOIN qualifying_purchase p ON c.client_id=p.client_id AND c.category_id=p.category_id
SETTINGS max_threads=1, max_memory_usage=1073741824, max_block_size=8192,
    join_algorithm='grace_hash', max_bytes_in_join=67108864, join_use_nulls=1,
    max_bytes_before_external_group_by=67108864, max_bytes_before_external_sort=33554432,
    max_insert_block_size=65536, min_insert_block_size_rows=65536,
    min_insert_block_size_bytes=16777216
