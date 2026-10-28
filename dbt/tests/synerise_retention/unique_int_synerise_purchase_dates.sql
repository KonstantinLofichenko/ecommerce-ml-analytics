{{ config(tags=['synerise_retention']) }}
SELECT client_id, purchase_date FROM {{ ref('int_synerise_purchase_dates') }} GROUP BY client_id, purchase_date HAVING count() > 1 SETTINGS optimize_aggregation_in_order = 1
