{{ config(tags=['synerise_retention']) }}
SELECT a.client_id
FROM {{ ref('int_synerise_customer_purchase_months') }} a
LEFT JOIN {{ ref('int_synerise_customer_first_purchase') }} f USING (client_id)
WHERE a.month_number < 0 OR a.cohort_month != f.cohort_month
 OR a.month_number != dateDiff('month', a.cohort_month, a.purchase_month)
 OR f.client_id IS NULL
SETTINGS join_use_nulls = 1
