{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['stage_order']
    )
}}

WITH funnel_counts AS (

    SELECT
        1 AS stage_order,
        'Page visit' AS stage,
        count() AS customers
    FROM {{ ref('int_synerise_funnel_first_visit') }}

    UNION ALL

    SELECT
        2 AS stage_order,
        'Add to cart' AS stage,
        count() AS customers
    FROM {{ ref('int_synerise_funnel_first_cart') }}

    UNION ALL

    SELECT
        3 AS stage_order,
        'Purchase' AS stage,
        count() AS customers
    FROM {{ ref('int_synerise_funnel_first_purchase') }}

),

with_previous AS (

    SELECT
        stage_order,
        stage,
        customers,
        first_value(customers) OVER (
            ORDER BY stage_order
        ) AS initial_customers,
        lagInFrame(customers, 1, customers) OVER (
            ORDER BY stage_order
            ROWS BETWEEN UNBOUNDED PRECEDING
                     AND UNBOUNDED FOLLOWING
        ) AS previous_customers
    FROM funnel_counts

)

SELECT
    stage_order,
    stage,
    customers,
    initial_customers,
    previous_customers,

    toFloat64(customers) / nullIf(previous_customers, 0)
        AS step_conversion_rate,

    toFloat64(customers) / nullIf(initial_customers, 0)
        AS overall_conversion_rate

FROM with_previous