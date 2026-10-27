-- Metabase native SQL, not dbt Jinja. Configure each category variable as a Field Filter
-- mapped to the identically named column on this reporting table (no table alias).
-- Numeric minimums: Number variables, suggested defaults 100 carts / 30 converters / 100 eligible.
SELECT sku,
    synthetic_product_title, category_id,
    synthetic_category_label,
    category_level_1, category_level_2, category_level_3, category_level_4,
    category_level_5, category_depth, category_leaf,
    cart_customers, converted_customers, eligible_customers_7d,
    p50_seconds / 60.0 AS p50_minutes,
    p75_seconds / 3600.0 AS p75_hours,
    p90_seconds / 86400.0 AS p90_days,
    avg_seconds / 3600.0 AS avg_hours,
    converted_1h, converted_24h, converted_7d,
    conversion_1h_rate, conversion_24h_rate, conversion_7d_rate
FROM synerise_analytics.fct_synerise_time_to_conversion_by_product
WHERE 1=1
[[AND {{category_level_1}}]]
[[AND {{category_level_2}}]]
[[AND {{category_level_3}}]]
[[AND {{category_level_4}}]]
[[AND cart_customers >= {{min_cart_customers}}]]
[[AND converted_customers >= {{min_converted_customers}}]]
[[AND eligible_customers_7d >= {{min_eligible_customers}}]]
ORDER BY converted_customers DESC, sku
LIMIT 100
