-- Deployed Metabase question: hierarchy Field Filters on this fact, no table alias.
-- Required Number min_eligible_customers defaults to 100; required Text rank_by defaults to rate.
-- Rank by accepts rate or volume; all rates/shares are fractions for Percentage formatting.
SELECT category_id, synthetic_category_label,
    concat(toString(category_id), ' | ', category_leaf) AS category_display,
    category_level_1, category_level_2, category_level_3, category_level_4,
    category_level_5, category_leaf,
    eligible_customers_7d, converted_1h, converted_24h, converted_7d,
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
    cart_customers AS all_time_cart_memberships,
    converted_customers AS all_time_converted_memberships,
    p50_seconds/60.0 AS all_converter_p50_minutes,
    p75_seconds/3600.0 AS all_converter_p75_hours,
    p90_seconds/86400.0 AS all_converter_p90_days
FROM synerise_analytics.fct_synerise_time_to_conversion_by_category
WHERE eligible_customers_7d >= {{min_eligible_customers}}
[[AND {{category_level_1}}]]
[[AND {{category_level_2}}]]
[[AND {{category_level_3}}]]
[[AND {{category_level_4}}]]
ORDER BY
    if({{rank_by}}='rate', abandonment_7d_rate, toFloat64(abandoned_7d)) DESC NULLS LAST,
    abandoned_7d DESC, category_id
LIMIT 100
