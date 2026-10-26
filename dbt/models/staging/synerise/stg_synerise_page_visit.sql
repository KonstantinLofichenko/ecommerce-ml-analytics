{{
    config(
        materialized='view'
    )
}}

SELECT
    client_id,
    timestamp AS event_time_raw,
    toDate(timestamp) AS event_date,
    timestamp AS event_time_source,
    url AS page_id
FROM {{ source('synerise', 'page_visit') }}