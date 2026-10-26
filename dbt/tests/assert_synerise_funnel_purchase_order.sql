SELECT
    client_id,
    first_visit_time,
    first_cart_time,
    first_purchase_time

FROM {{ ref('int_synerise_funnel_first_purchase') }}

WHERE first_cart_time < first_visit_time
   OR first_purchase_time < first_cart_time