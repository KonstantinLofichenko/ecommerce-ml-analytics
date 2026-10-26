{{
    config(
        tags=['synthetic_catalog']
    )
}}
WITH pool AS ({{ amazon_synthetic_pool() }})
SELECT toString(p.sku) AS id
FROM {{ ref('dim_synerise_products') }} AS p
LEFT JOIN pool AS a ON p.amazon_parent_asin = a.parent_asin
LEFT JOIN {{ ref('stg_amazon_products') }} AS d ON p.amazon_parent_asin = d.parent_asin
WHERE a.parent_asin IS NULL OR d.parent_asin IS NULL
    OR p.amazon_category_key != a.amazon_category_key
    OR p.amazon_source_department != a.source_department
    OR p.synthetic_product_title != d.product_name
    OR p.amazon_classification_status != a.classification_status
    OR p.amazon_main_category_conflict != a.main_category_conflict
    OR modulo(cityHash64('amazon_catalog_v1:product', toString(p.sku)),
        a.category_product_count) + 1 != a.category_product_index
SETTINGS join_use_nulls = 1, max_threads = 1, max_block_size = 8192,
    max_memory_usage = 1073741824, join_algorithm = 'hash', max_bytes_in_join = 134217728
