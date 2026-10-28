{{ config(tags=['synerise_retention']) }}
SELECT r.cohort_month, r.month_number
FROM {{ ref('fct_synerise_customer_monthly_retention') }} r
LEFT JOIN (
 SELECT cohort_month, month_number, count() AS n
 FROM {{ ref('int_synerise_customer_purchase_months') }} GROUP BY cohort_month, month_number
) a USING (cohort_month, month_number)
WHERE r.retained_customers != coalesce(a.n, 0)
 OR r.retained_customers > r.cohort_size OR r.retention_rate < 0 OR r.retention_rate > 1
 OR abs(r.retention_rate - toFloat64(r.retained_customers)/nullIf(r.cohort_size,0)) > 1e-12
 OR (r.month_number=0 AND (r.retained_customers!=r.cohort_size OR r.retention_rate!=1))
