SELECT
    client_id,
    event_time_raw
FROM {{ ref('stg_synerise_search_query') }}
WHERE length(query_codes) != 16