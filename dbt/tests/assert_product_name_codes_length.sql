SELECT
    sku,
    length(name_codes) AS code_count
FROM {{ ref('stg_synerise_product_properties') }}
WHERE length(name_codes) != 16