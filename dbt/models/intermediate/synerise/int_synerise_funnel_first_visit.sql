{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id']
    )
}}

SELECT
    client_id,
    min(event_time_source) AS first_visit_time
FROM {{ ref('stg_synerise_page_visit') }}
GROUP BY client_id