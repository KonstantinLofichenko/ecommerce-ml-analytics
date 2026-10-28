{{ config(tags=['synerise_retention']) }}
SELECT cohort_month, month_number FROM {{ ref('fct_synerise_customer_monthly_retention') }} GROUP BY cohort_month, month_number HAVING count() > 1 SETTINGS optimize_aggregation_in_order = 1
