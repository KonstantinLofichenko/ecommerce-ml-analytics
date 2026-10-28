{{ config(tags=['synerise_retention']) }}
WITH sizes AS (
 SELECT cohort_month,count() AS n FROM {{ ref('int_synerise_customer_first_purchase') }} GROUP BY cohort_month
), expected AS (
 SELECT s.cohort_month, arrayJoin(range(toUInt32({{ var('synerise_retention_months',12) }}+1))) AS month_number
 FROM sizes s CROSS JOIN {{ ref('int_synerise_purchase_observation_window') }} w
 WHERE s.cohort_month > toStartOfMonth(w.observed_start_date)
 AND addMonths(s.cohort_month,toInt32(month_number)) < toStartOfMonth(w.observed_end_date)
)
SELECT e.cohort_month,e.month_number FROM expected e
FULL OUTER JOIN {{ ref('fct_synerise_customer_monthly_retention') }} r USING(cohort_month,month_number)
LEFT JOIN sizes s ON r.cohort_month=s.cohort_month
WHERE e.cohort_month IS NULL OR r.cohort_month IS NULL OR r.cohort_size!=s.n
 OR r.purchase_month!=addMonths(r.cohort_month,toInt32(r.month_number)) OR r.coverage_verified!=0
SETTINGS join_use_nulls=1
