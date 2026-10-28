{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id']
    )
}}

SELECT client_id,
    min(first_purchase_at) AS first_purchase_at,
    min(purchase_date) AS first_purchase_date,
    toStartOfMonth(first_purchase_date) AS cohort_month
FROM {{ ref('int_synerise_purchase_dates') }}
GROUP BY client_id
