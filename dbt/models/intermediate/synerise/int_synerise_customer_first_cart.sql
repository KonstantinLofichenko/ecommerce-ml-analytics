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

SETTINGS
    max_threads = 1,
    max_memory_usage = 1073741824,
    max_bytes_before_external_group_by = 268435456