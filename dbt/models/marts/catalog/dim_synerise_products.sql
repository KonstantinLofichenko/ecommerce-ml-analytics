{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['sku'],
        tags=['synthetic_catalog'],
        meta={'synthetic': true, 'exclude_from_ml': true}
    )
}}

WITH catalog AS ({{ amazon_synthetic_pool() }}),
assignments AS (
    -- Keep assignment joins narrow; attach long display strings only at the end.
    SELECT p.sku, p.category_id, p.price_bucket, c.amazon_category_index,
        modulo(cityHash64('amazon_catalog_v1:product', toString(p.sku)),
            c.amazon_category_product_count) + 1 AS category_product_index
    FROM {{ ref('stg_synerise_product_properties') }} AS p
    INNER JOIN {{ ref('dim_synerise_categories') }} AS c ON p.category_id = c.category_id
), chosen AS (
    SELECT a.sku, a.category_id, a.price_bucket,
        c.parent_asin, c.classification_status, c.main_category_conflict
    FROM assignments AS a
    INNER JOIN (
        SELECT parent_asin, amazon_category_index, category_product_index,
            classification_status, main_category_conflict
        FROM catalog
    ) AS c
        ON a.amazon_category_index = c.amazon_category_index
        AND a.category_product_index = c.category_product_index
)
SELECT
    p.sku AS sku, p.category_id AS category_id, p.price_bucket AS price_bucket,
    c.synthetic_category_label AS synthetic_category_label,
    c.synthetic_category_path AS synthetic_category_path,
    {{ inherited_category_hierarchy('c') }},
    c.amazon_category_key AS amazon_category_key,
    c.amazon_source_department AS amazon_source_department,
    p.parent_asin AS amazon_parent_asin,
    a.product_name AS synthetic_product_title,
    p.classification_status AS amazon_classification_status,
    p.main_category_conflict AS amazon_main_category_conflict,
    toUInt8(1) AS is_synthetic_enrichment,
    'amazon_catalog_v1' AS mapping_version
FROM chosen AS p
INNER JOIN {{ ref('dim_synerise_categories') }} AS c ON p.category_id = c.category_id
INNER JOIN {{ ref('stg_amazon_products') }} AS a ON p.parent_asin = a.parent_asin
SETTINGS max_threads = 1, max_block_size = 8192, max_memory_usage = 1073741824,
    max_insert_block_size = 65536, min_insert_block_size_rows = 65536,
    min_insert_block_size_bytes = 16777216,
    join_algorithm = 'hash', max_bytes_in_join = 134217728,
    max_bytes_before_external_sort = 33554432
