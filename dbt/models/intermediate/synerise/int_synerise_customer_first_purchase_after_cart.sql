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
