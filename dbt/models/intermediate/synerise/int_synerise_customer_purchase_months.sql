{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id', 'purchase_month']
    )
}}

SELECT d.client_id AS client_id,
    toStartOfMonth(d.purchase_date) AS purchase_month,
    f.cohort_month AS cohort_month,
    dateDiff('month', f.cohort_month, purchase_month) AS month_number
FROM {{ ref('int_synerise_purchase_dates') }} AS d
INNER JOIN {{ ref('int_synerise_customer_first_purchase') }} AS f
    ON d.client_id = f.client_id
GROUP BY client_id, purchase_month, cohort_month
