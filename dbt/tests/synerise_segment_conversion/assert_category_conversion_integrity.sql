SELECT category_id, client_id
FROM {{ ref('int_synerise_category_conversion_times') }}
WHERE (converted=0 AND (first_purchase_time IS NOT NULL OR seconds_to_conversion IS NOT NULL))
    OR (converted=1 AND (first_purchase_time IS NULL OR seconds_to_conversion IS NULL))
    OR first_purchase_time < first_cart_time OR seconds_to_conversion < 0
    OR seconds_to_conversion != dateDiff('second', first_cart_time, first_purchase_time)
