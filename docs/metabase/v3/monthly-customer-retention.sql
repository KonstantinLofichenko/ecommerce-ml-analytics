-- Reconstructed from GUI/MBQL saved question 60; not generated original SQL.
SELECT
    cohort_month,
    month_number,
    sum(retention_rate) AS sum
FROM synerise_analytics.fct_synerise_customer_monthly_retention
GROUP BY cohort_month, month_number
