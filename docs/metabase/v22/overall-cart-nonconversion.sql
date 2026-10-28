-- Genuine first-cart customer cohort; intentionally no category/SKU/date filters.
-- Rates/shares are fractions: configure Metabase Percentage, never multiply by 100.
SELECT eligible_customers_7d, converted_1h, converted_24h, converted_7d,
    toInt64(eligible_customers_7d)-toInt64(converted_1h) AS abandoned_1h,
    toInt64(eligible_customers_7d)-toInt64(converted_24h) AS abandoned_24h,
    toInt64(eligible_customers_7d)-toInt64(converted_7d) AS abandoned_7d,
    toFloat64(abandoned_1h)/nullIf(eligible_customers_7d,0) AS abandonment_1h_rate,
    toFloat64(abandoned_24h)/nullIf(eligible_customers_7d,0) AS abandonment_24h_rate,
    toFloat64(abandoned_7d)/nullIf(eligible_customers_7d,0) AS abandonment_7d_rate,
    toFloat64(converted_1h)/nullIf(converted_7d,0) AS early_conversion_share,
    toInt64(converted_1h) AS within_1h_customers,
    toInt64(converted_24h)-toInt64(converted_1h) AS between_1h_24h_customers,
    toInt64(converted_7d)-toInt64(converted_24h) AS between_24h_7d_customers,
    abandoned_7d AS not_converted_7d_customers,
    toFloat64(within_1h_customers)/nullIf(eligible_customers_7d,0) AS within_1h_share,
    toFloat64(between_1h_24h_customers)/nullIf(eligible_customers_7d,0) AS between_1h_24h_share,
    toFloat64(between_24h_7d_customers)/nullIf(eligible_customers_7d,0) AS between_24h_7d_share,
    toFloat64(not_converted_7d_customers)/nullIf(eligible_customers_7d,0) AS not_converted_7d_share,
    p50_minutes, p75_minutes/60.0 AS p75_hours, p90_minutes/1440.0 AS p90_days
FROM synerise_analytics.fct_synerise_time_to_conversion
WHERE metric_scope='customer'
