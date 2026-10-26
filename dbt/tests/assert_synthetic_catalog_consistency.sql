{{
    config(
        tags=['synthetic_catalog']
    )
}}
SELECT toString(p.sku) AS id
FROM {{ ref('dim_synerise_products') }} AS p
INNER JOIN {{ ref('dim_synerise_categories') }} AS c ON p.category_id = c.category_id
WHERE p.amazon_category_key != c.amazon_category_key
    OR p.synthetic_category_path != c.synthetic_category_path
    OR p.synthetic_category_label != c.synthetic_category_label
    OR p.amazon_source_department != c.amazon_source_department
    OR p.category_depth != c.category_depth OR p.category_leaf != c.category_leaf
{% for level in range(1, 6) %}
    OR p.category_level_{{ level }} != c.category_level_{{ level }}
{% endfor %}
SETTINGS max_threads = 1, max_block_size = 8192, max_memory_usage = 1073741824,
    join_algorithm = 'grace_hash', max_bytes_in_join = 67108864
