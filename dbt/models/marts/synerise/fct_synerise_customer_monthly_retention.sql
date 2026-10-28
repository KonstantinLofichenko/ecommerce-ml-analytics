{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['cohort_month', 'month_number']
    )
}}

{% set horizon = var('synerise_retention_months', 12) | int %}
{% if horizon < 0 or horizon > 120 %}
    {{ exceptions.raise_compiler_error('synerise_retention_months must be between 0 and 120') }}
{% endif %}
WITH cohorts AS (
    SELECT cohort_month, count() AS cohort_size
    FROM {{ ref('int_synerise_customer_first_purchase') }}
    GROUP BY cohort_month
), activity AS (
    SELECT cohort_month, month_number, count() AS retained_customers
    FROM {{ ref('int_synerise_customer_purchase_months') }}
    GROUP BY cohort_month, month_number
), grid AS (
    SELECT c.cohort_month AS cohort_month, c.cohort_size AS cohort_size,
        arrayJoin(range(toUInt32({{ horizon }} + 1))) AS month_number,
        addMonths(c.cohort_month, toInt32(month_number)) AS purchase_month,
        w.coverage_policy AS coverage_policy, w.coverage_verified AS coverage_verified
    FROM cohorts AS c
    CROSS JOIN {{ ref('int_synerise_purchase_observation_window') }} AS w
    -- Boundary months are excluded conservatively, even if activity is at midnight.
    WHERE c.cohort_month > toStartOfMonth(w.observed_start_date)
      AND c.cohort_month < toStartOfMonth(w.observed_end_date)
      AND purchase_month < toStartOfMonth(w.observed_end_date)
)
SELECT g.cohort_month AS cohort_month, g.purchase_month AS purchase_month,
    g.month_number AS month_number, g.cohort_size AS cohort_size,
    coalesce(a.retained_customers, toUInt64(0)) AS retained_customers,
    toFloat64(retained_customers) / nullIf(g.cohort_size, 0) AS retention_rate,
    g.coverage_policy AS coverage_policy, g.coverage_verified AS coverage_verified
FROM grid AS g
LEFT JOIN activity AS a
    ON g.cohort_month = a.cohort_month AND g.month_number = a.month_number
