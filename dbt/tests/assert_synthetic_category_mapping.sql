{{
    config(
        tags=['synthetic_catalog']
    )
}}
WITH pool AS ({{ amazon_synthetic_pool() }})
SELECT 'category_anchor_or_label_mismatch', toString(c.category_id)
FROM {{ ref('dim_synerise_categories') }} AS c
LEFT JOIN pool AS a ON c.amazon_anchor_parent_asin = a.parent_asin
WHERE a.parent_asin IS NULL
    OR c.amazon_category_key != a.amazon_category_key
    OR c.amazon_category_index != a.amazon_category_index
    OR c.synthetic_category_path != JSONExtract(ifNull(a.amazon_category_key, '[]'), 2, 'Array(String)')
    OR c.amazon_source_department != a.source_department
    OR c.amazon_anchor_classification_status != a.classification_status
    OR c.amazon_category_product_count != a.category_product_count
    OR c.synthetic_category_label != concat('Synthetic: ', arrayStringConcat(JSONExtract(ifNull(a.amazon_category_key, '[]'), 2, 'Array(String)'), ' > '))
    OR modulo(cityHash64('amazon_catalog_v1:category', toString(c.category_id)),
        a.catalog_product_count) + 1 != a.catalog_index
SETTINGS join_use_nulls = 1, max_threads = 1, max_block_size = 8192,
    max_memory_usage = 1073741824, join_algorithm = 'hash', max_bytes_in_join = 134217728
