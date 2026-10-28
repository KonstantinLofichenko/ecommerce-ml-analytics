{{ config(tags=['synerise_retention']) }}
SELECT client_id, purchase_month FROM {{ ref('int_synerise_customer_purchase_months') }} GROUP BY client_id, purchase_month HAVING count() > 1 SETTINGS optimize_aggregation_in_order = 1
