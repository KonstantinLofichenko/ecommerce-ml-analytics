WITH
first_cart AS (
    SELECT count() AS n
    FROM {{ ref('int_synerise_customer_first_cart') }}
),

first_purchase AS (
    SELECT count() AS n
    FROM {{ ref('int_synerise_customer_first_purchase_after_cart') }}
),

conversion AS (
    SELECT
        count() AS total,
        countIf(converted = 1) AS purchased
    FROM {{ ref('int_synerise_customer_conversion_times') }}
)

SELECT
    first_cart.n AS first_cart_customers,
    first_purchase.n AS first_purchase_customers,
    conversion.total AS conversion_customers,
    conversion.purchased AS converted_customers

FROM first_cart
CROSS JOIN first_purchase
CROSS JOIN conversion

WHERE
       first_cart.n != conversion.total
    OR first_purchase.n != conversion.purchased