{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['sku'],
        meta={'synthetic_display_fields': true, 'exclude_from_ml': true}
    )
}}
SELECT
    f.sku AS sku,
    d.category_id AS category_id,
    d.synthetic_product_title AS synthetic_product_title,
    d.synthetic_category_path AS synthetic_category_path,
    d.synthetic_category_label AS synthetic_category_label,
    {{ inherited_category_hierarchy('d') }},
    f.cart_customers AS cart_customers,
    f.purchase_customers AS purchase_customers,
    f.conversion_rate AS conversion_rate
FROM {{ ref('int_synerise_product_funnel_metrics') }} AS f
LEFT JOIN {{ ref('dim_synerise_products') }} AS d ON f.sku = d.sku
