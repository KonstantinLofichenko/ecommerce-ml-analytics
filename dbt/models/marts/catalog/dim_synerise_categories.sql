{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['category_id'],
        tags=['synthetic_catalog'],
        meta={'synthetic': true, 'exclude_from_ml': true}
    )
}}

WITH catalog AS ({{ amazon_synthetic_pool() }}),
category_ids AS (
    SELECT DISTINCT category_id FROM {{ ref('stg_synerise_product_properties') }}
), assignments AS (
    SELECT category_id,
        modulo(cityHash64('amazon_catalog_v1:category', toString(category_id)),
            nullIf((SELECT max(catalog_product_count) FROM catalog), 0)) + 1 AS catalog_index
    FROM category_ids
), mapped_categories AS (
SELECT
    a.category_id,
    concat('Synthetic: ', arrayStringConcat(JSONExtract(c.amazon_category_key, 2, 'Array(String)'), ' > '))
        AS synthetic_category_label,
    JSONExtract(c.amazon_category_key, 2, 'Array(String)') AS synthetic_category_path,
    c.amazon_category_key,
    c.amazon_category_index,
    c.source_department AS amazon_source_department,
    c.parent_asin AS amazon_anchor_parent_asin,
    c.classification_status AS amazon_anchor_classification_status,
    c.category_product_count AS amazon_category_product_count,
    toUInt8(1) AS is_synthetic_enrichment,
    'amazon_catalog_v1' AS mapping_version
FROM assignments AS a
INNER JOIN catalog AS c ON a.catalog_index = c.catalog_index
)
SELECT *,
    {{ category_hierarchy('synthetic_category_path') }}
FROM mapped_categories
SETTINGS max_threads = 1, max_block_size = 8192, max_memory_usage = 1073741824,
    max_insert_block_size = 65536, min_insert_block_size_rows = 65536,
    min_insert_block_size_bytes = 16777216,
    join_algorithm = 'hash', max_bytes_in_join = 134217728,
    max_bytes_before_external_sort = 33554432
