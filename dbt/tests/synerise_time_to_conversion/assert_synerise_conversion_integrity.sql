SELECT
    client_id,
    first_cart_time,
    first_purchase_time,
    converted,
    seconds_to_conversion

FROM {{ ref('int_synerise_customer_conversion_times') }}

WHERE
       (converted = 1 AND first_purchase_time IS NULL)
    OR (converted = 0 AND first_purchase_time IS NOT NULL)
    OR (converted = 1 AND seconds_to_conversion IS NULL)
    OR (converted = 0 AND seconds_to_conversion IS NOT NULL)
    OR (seconds_to_conversion < 0)
    OR (
        first_purchase_time IS NOT NULL
        AND first_purchase_time < first_cart_time
    )
    OR (
        converted = 1
        AND seconds_to_conversion != dateDiff(
            'second',
            first_cart_time,
            first_purchase_time
        )
    )