SELECT
    p.client_id,
    c.first_cart_time,
    p.first_purchase_time

FROM {{ ref('int_synerise_customer_first_purchase_after_cart') }} AS p

INNER JOIN {{ ref('int_synerise_customer_first_cart') }} AS c
    ON p.client_id = c.client_id

WHERE p.first_purchase_time < c.first_cart_time