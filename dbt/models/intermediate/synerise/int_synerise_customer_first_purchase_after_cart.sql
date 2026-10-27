{{ config(
    materialized='table',
    engine='MergeTree()',
    order_by=['client_id']
) }}

SELECT
    p.client_id AS client_id,

    min(
        parseDateTimeBestEffort(p.timestamp)
    ) AS first_purchase_time

FROM {{ source('synerise', 'product_buy') }} as p

INNER JOIN {{
    ref('int_synerise_customer_first_cart')
}} AS c
    ON p.client_id = c.client_id

WHERE
    parseDateTimeBestEffort(p.timestamp)
        >= c.first_cart_time

GROUP BY
    p.client_id

SETTINGS
    max_threads = 1,
    max_memory_usage = 1073741824,
    join_algorithm = 'grace_hash',
    max_bytes_in_join = 67108864,
    max_bytes_before_external_group_by = 268435456