SELECT
    client_id,
    first_visit_time,
    first_cart_time
FROM {{ ref('int_synerise_funnel_first_cart') }}
WHERE first_cart_time < first_visit_time