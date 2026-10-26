{{
    config(
        materialized='view'
    )
}}

SELECT
    sku,
    category AS category_id,
    price AS price_bucket,
    name AS name_encoded,

    arrayMap(
        x -> toUInt8(x),
        splitByWhitespace(
            replaceRegexpAll(name, '[\\[\\]]', '')
        )
    ) AS name_codes

FROM {{ source('synerise', 'product_properties') }}