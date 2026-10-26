{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id']
    )
}}

SELECT
    c.client_id,
    c.first_visit_time,
    c.first_cart_time,
    min(p.event_time_source) AS first_purchase_time

FROM {{ ref('int_synerise_funnel_first_cart') }} AS c

INNER JOIN {{ ref('stg_synerise_product_buy') }} AS p
    ON c.client_id = p.client_id

WHERE p.event_time_source >= c.first_cart_time

GROUP BY
    c.client_id,
    c.first_visit_time,
    c.first_cart_time