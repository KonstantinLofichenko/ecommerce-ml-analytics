{{ config(
    materialized='table',
    engine='MergeTree()',
    order_by=['metric_scope']
) }}

WITH
    toDateTime('2022-12-08 00:09:59') AS dataset_end,

summary AS (
    SELECT
        count() AS cart_customers,

        countIf(converted = 1)
            AS converted_customers,

        round(
            avgIf(
                seconds_to_conversion,
                converted = 1
            ) / 60.0,
            2
        ) AS avg_minutes,

        round(
            quantileExactIf(0.50)(
                seconds_to_conversion,
                converted = 1
            ) / 60.0,
            2
        ) AS p50_minutes,

        round(
            quantileExactIf(0.75)(
                seconds_to_conversion,
                converted = 1
            ) / 60.0,
            2
        ) AS p75_minutes,

        round(
            quantileExactIf(0.90)(
                seconds_to_conversion,
                converted = 1
            ) / 60.0,
            2
        ) AS p90_minutes,

        countIf(
            first_cart_time <=
                dataset_end - INTERVAL 7 DAY
        ) AS eligible_customers_7d,

        countIf(
            first_cart_time <=
                dataset_end - INTERVAL 7 DAY
            AND converted = 1
            AND seconds_to_conversion <= 3600
        ) AS converted_1h,

        countIf(
            first_cart_time <=
                dataset_end - INTERVAL 7 DAY
            AND converted = 1
            AND seconds_to_conversion <= 86400
        ) AS converted_24h,

        countIf(
            first_cart_time <=
                dataset_end - INTERVAL 7 DAY
            AND converted = 1
            AND seconds_to_conversion <= 604800
        ) AS converted_7d

    FROM {{
        ref('int_synerise_customer_conversion_times')
    }}
)

SELECT
    'customer' AS metric_scope,

    cart_customers,
    converted_customers,

    avg_minutes,
    p50_minutes,
    p75_minutes,
    p90_minutes,

    eligible_customers_7d,

    converted_1h,
    converted_24h,
    converted_7d,

    round(
        converted_1h /
        nullIf(eligible_customers_7d, 0),
        5
    ) AS conversion_1h_pct,

    round(
        converted_24h /
        nullIf(eligible_customers_7d, 0),
        5
    ) AS conversion_24h_pct,

    round(
        converted_7d /
        nullIf(eligible_customers_7d, 0),
        5
    ) AS conversion_7d_pct

FROM summary

SETTINGS
    max_threads = 1,
    max_memory_usage = 1073741824