WITH
    (
        SELECT max(last_purchase_date)
        FROM synerise_analytics.fct_synerise_customer_repeat_purchase
    ) AS observation_end_date

SELECT
    cohort_month,
    count() AS eligible_customers,
    countIf(
        days_to_second_purchase_date BETWEEN 1 AND 30
    ) AS repeat_customers_30d,
    round(
        repeat_customers_30d
        / nullIf(eligible_customers, 0),
        4
    ) AS repeat_purchase_rate_30d_pct
FROM synerise_analytics.fct_synerise_customer_repeat_purchase
WHERE first_purchase_date <= subtractDays(observation_end_date, 30)
GROUP BY cohort_month
ORDER BY cohort_month;
