{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id', 'purchase_date']
    )
}}

-- One row per customer/source-clock purchase date; raw multiplicity is not orders.
SELECT client_id,
    toDate(substring(event_time_source, 1, 10)) AS purchase_date,
    min(event_time_source) AS first_purchase_at
FROM {{ ref('stg_synerise_product_buy') }}
WHERE match(event_time_source, '^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$')
    AND isNotNull(parseDateTimeBestEffortOrNull(event_time_source))
GROUP BY client_id, purchase_date
