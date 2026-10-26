{{
    config(
        materialized='view'
    )
}}

SELECT
    parent_asin,
    title AS product_name,
    source_department,

    if(
        length(categories) >= 2,
        ifNull(categories[2], ''),
        ''
    ) AS category_name,

    if(
        length(categories) >= 3,
        ifNull(categories[3], ''),
        ''
    ) AS subcategory_name,

    main_category,
    store AS brand_or_store

FROM {{ source('amazon', 'amazon_products') }}
WHERE title != ''
  AND parent_asin != ''