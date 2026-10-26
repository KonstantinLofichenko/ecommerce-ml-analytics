{{
    config(
        tags=['synthetic_catalog']
    )
}}
-- FULL OUTER JOIN checks both missing and unexpected IDs; raw attributes stay real.
SELECT 'product_coverage_or_real_attribute_changed' AS issue, toString(coalesce(p.sku, d.sku)) AS id
FROM {{ ref('stg_synerise_product_properties') }} AS p
FULL OUTER JOIN {{ ref('dim_synerise_products') }} AS d ON p.sku = d.sku
WHERE p.sku IS NULL OR d.sku IS NULL OR p.category_id != d.category_id OR p.price_bucket != d.price_bucket
UNION ALL
SELECT 'category_coverage', toString(coalesce(c.category_id, d.category_id))
FROM (SELECT DISTINCT category_id FROM {{ ref('stg_synerise_product_properties') }}) AS c
FULL OUTER JOIN {{ ref('dim_synerise_categories') }} AS d ON c.category_id = d.category_id
WHERE c.category_id IS NULL OR d.category_id IS NULL
SETTINGS join_use_nulls = 1
