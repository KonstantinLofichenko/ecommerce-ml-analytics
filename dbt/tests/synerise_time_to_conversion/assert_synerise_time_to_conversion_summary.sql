WITH
    toDateTime('2022-12-08 00:09:59') AS dataset_end,

expected AS (
    SELECT
        count() AS cart_customers,
        countIf(converted = 1) AS converted_customers,

        countIf(
            first_cart_time <= dataset_end - INTERVAL 7 DAY
        ) AS eligible_customers_7d,

        countIf(
            first_cart_time <= dataset_end - INTERVAL 7 DAY
            AND converted = 1
            AND seconds_to_conversion <= 3600
        ) AS converted_1h,

        countIf(
            first_cart_time <= dataset_end - INTERVAL 7 DAY
            AND converted = 1
            AND seconds_to_conversion <= 86400
        ) AS converted_24h,

        countIf(
            first_cart_time <= dataset_end - INTERVAL 7 DAY
            AND converted = 1
            AND seconds_to_conversion <= 604800
        ) AS converted_7d

    FROM {{ ref('int_synerise_customer_conversion_times') }}
)

SELECT
    f.metric_scope,
    f.cart_customers,
    f.converted_customers,
    f.eligible_customers_7d

FROM {{ ref('fct_synerise_time_to_conversion') }} AS f
CROSS JOIN expected AS e

WHERE
       f.cart_customers != e.cart_customers
    OR f.converted_customers != e.converted_customers
    OR f.eligible_customers_7d != e.eligible_customers_7d
    OR f.converted_1h != e.converted_1h
    OR f.converted_24h != e.converted_24h
    OR f.converted_7d != e.converted_7d
    OR NOT (
        f.converted_1h <= f.converted_24h
        AND f.converted_24h <= f.converted_7d
        AND f.converted_7d <= f.eligible_customers_7d
    )