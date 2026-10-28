{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['client_id']
    )
}}

SELECT d.client_id AS client_id,
    f.cohort_month AS cohort_month,
    min(d.purchase_date) AS first_purchase_date,
    max(d.purchase_date) AS last_purchase_date,
    count() AS distinct_purchase_dates,
    uniqExact(toStartOfMonth(d.purchase_date)) AS active_purchase_months,
    toUInt8(distinct_purchase_dates >= 2) AS is_repeat_purchaser,
    if(distinct_purchase_dates >= 2,
       dateDiff('day', first_purchase_date,
          arrayElement(arraySort(groupArray(d.purchase_date)), 2)), NULL)
        AS days_to_second_purchase_date
FROM {{ ref('int_synerise_purchase_dates') }} AS d
INNER JOIN {{ ref('int_synerise_customer_first_purchase') }} AS f
    ON d.client_id = f.client_id
GROUP BY client_id, cohort_month
