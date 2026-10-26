{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id']
    )
}}

SELECT
    v.client_id,
    v.first_visit_time,
    min(c.event_time_source) AS first_cart_time
FROM {{ ref('int_synerise_funnel_first_visit') }} AS v
INNER JOIN {{ ref('stg_synerise_add_to_cart') }} AS c
    ON v.client_id = c.client_id
WHERE c.event_time_source >= v.first_visit_time
GROUP BY
    v.client_id,
    v.first_visit_time