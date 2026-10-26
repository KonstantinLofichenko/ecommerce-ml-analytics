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
    query AS query_encoded,

    arrayMap(
        x -> toUInt8(x),
        splitByWhitespace(
            replaceRegexpAll(query, '[\\[\\]]', '')
        )
    ) AS query_codes

FROM {{ source('synerise', 'search_query') }}