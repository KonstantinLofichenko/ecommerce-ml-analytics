WITH
    (
        SELECT max(toDate(last_purchase_date))
        FROM synerise_analytics.fct_synerise_customer_repeat_purchase
    ) AS observation_end_date,

    first_purchase_metrics AS (
        SELECT
            count() AS total_customers,
            countIf(is_repeat_purchaser = 1) AS repeat_purchasers,
            quantileExactIf(0.50)(
                days_to_second_purchase_date,
                is_repeat_purchaser = 1
            ) AS median_days_to_second_purchase
        FROM synerise_analytics.fct_synerise_customer_repeat_purchase
    ),

    repeat_30d_metrics AS (
        SELECT
            count() AS eligible_customers_30d,
            countIf(
                days_to_second_purchase_date BETWEEN 1 AND 30
            ) AS repeat_purchasers_30d
        FROM synerise_analytics.fct_synerise_customer_repeat_purchase
        WHERE first_purchase_date <= subtractDays(observation_end_date, 30)
    )

SELECT
    round(
        f.repeat_purchasers / nullIf(f.total_customers, 0),
        4
    ) AS observed_repeat_purchase_rate_pct,

    f.repeat_purchasers,

    f.median_days_to_second_purchase,

    round(
        r.repeat_purchasers_30d / nullIf(r.eligible_customers_30d, 0),
        4
    ) AS repeat_purchase_rate_30d_pct

FROM first_purchase_metrics AS f
CROSS JOIN repeat_30d_metrics AS r;
