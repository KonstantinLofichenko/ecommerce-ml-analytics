{{ config(
    materialized='table',
    engine='MergeTree()',
    order_by=['client_id']
) }}

SELECT
    client_id,
    min(parseDateTimeBestEffort(timestamp)) AS first_cart_time

FROM {{ source('synerise', 'add_to_cart') }}

GROUP BY client_id
