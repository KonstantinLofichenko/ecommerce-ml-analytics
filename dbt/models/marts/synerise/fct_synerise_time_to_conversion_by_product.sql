{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['sku'],
        meta={'synthetic_display_fields': true, 'exclude_from_ml': true}
    )
}}
WITH metrics AS (
    {{ synerise_segment_summary(ref('int_synerise_product_conversion_times'), 'sku') }}
)
SELECT m.sku AS sku,
    m.cart_customers AS cart_customers,
    m.converted_customers AS converted_customers,
    m.avg_seconds AS avg_seconds,
    m.p50_seconds AS p50_seconds,
    m.p75_seconds AS p75_seconds,
    m.p90_seconds AS p90_seconds,
    m.eligible_customers_7d AS eligible_customers_7d,
    m.converted_1h AS converted_1h,
    m.conversion_1h_rate AS conversion_1h_rate,
    m.converted_24h AS converted_24h,
    m.conversion_24h_rate AS conversion_24h_rate,
    m.converted_7d AS converted_7d,
    m.conversion_7d_rate AS conversion_7d_rate,
    d.category_id AS category_id, d.synthetic_product_title AS synthetic_product_title,
    d.synthetic_category_label AS synthetic_category_label,
    d.synthetic_category_path AS synthetic_category_path,
    {{ inherited_category_hierarchy('d') }}
FROM metrics m
LEFT JOIN {{ ref('dim_synerise_products') }} d ON m.sku=d.sku
SETTINGS max_threads=1, max_memory_usage=1073741824, max_block_size=8192,
    join_algorithm='grace_hash', max_bytes_in_join=67108864, join_use_nulls=0,
    max_bytes_before_external_group_by=67108864, max_bytes_before_external_sort=33554432,
    max_insert_block_size=65536, min_insert_block_size_rows=65536,
    min_insert_block_size_bytes=16777216, optimize_aggregation_in_order=1
