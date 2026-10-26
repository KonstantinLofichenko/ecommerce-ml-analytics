{{
    config(
        materialized='view'
    )
}}

SELECT
    client_id,
    event_time_source,
    event_date,
    'page_visit' AS event_type,
    CAST(NULL AS Nullable(Int64)) AS sku,
    page_id
FROM {{ ref('stg_synerise_page_visit') }}

UNION ALL

SELECT
    client_id,
    event_time_source,
    event_date,
    'add_to_cart' AS event_type,
    sku,
    CAST(NULL AS Nullable(Int64)) AS page_id
FROM {{ ref('stg_synerise_add_to_cart') }}

UNION ALL

SELECT
    client_id,
    event_time_source,
    event_date,
    'remove_from_cart' AS event_type,
    sku,
    CAST(NULL AS Nullable(Int64)) AS page_id
FROM {{ ref('stg_synerise_remove_from_cart') }}

UNION ALL

SELECT
    client_id,
    event_time_source,
    event_date,
    'product_buy' AS event_type,
    sku,
    CAST(NULL AS Nullable(Int64)) AS page_id
FROM {{ ref('stg_synerise_product_buy') }}