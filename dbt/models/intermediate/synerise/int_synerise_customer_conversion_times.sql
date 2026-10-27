{{ config(
    materialized='table',
    engine='MergeTree()',
    order_by=['client_id']
) }}

SELECT
    c.client_id AS client_id,
    c.first_cart_time AS first_cart_time,

    p.first_purchase_time AS first_purchase_time,

    isNotNull(p.first_purchase_time) AS converted,

    if(
        isNotNull(p.first_purchase_time),
        dateDiff(
            'second',
            c.first_cart_time,
            p.first_purchase_time
        ),
        NULL
    ) AS seconds_to_conversion

FROM {{
    ref('int_synerise_customer_first_cart')
}} AS c

LEFT JOIN {{
    ref('int_synerise_customer_first_purchase_after_cart')
}} AS p
    ON c.client_id = p.client_id

SETTINGS
    join_use_nulls = 1,
    max_threads = 1,
    max_memory_usage = 1073741824,
    join_algorithm = 'grace_hash',
    max_bytes_in_join = 67108864