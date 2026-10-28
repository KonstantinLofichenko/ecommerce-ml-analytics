SELECT
    multiIf(
        seconds_to_conversion <= 3600, 1,
        seconds_to_conversion <= 86400, 2,
        seconds_to_conversion <= 604800, 3,
        4
    ) AS time_order,
    multiIf(
        seconds_to_conversion <= 3600, 'Within 1 hour',
        seconds_to_conversion <= 86400, '1–24 hours',
        seconds_to_conversion <= 604800, '1–7 days',
        'More than 7 days'
    ) AS time_bucket,
    count() AS converted_customers
FROM synerise_analytics.int_synerise_customer_conversion_times
WHERE converted = 1
GROUP BY time_order, time_bucket
ORDER BY time_order;