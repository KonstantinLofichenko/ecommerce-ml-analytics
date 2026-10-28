{{ config(tags=['synerise_retention']) }}
SELECT r.client_id FROM {{ ref('fct_synerise_customer_repeat_purchase') }} r
INNER JOIN (
 SELECT client_id,count() AS dates,uniqExact(toStartOfMonth(purchase_date)) AS months,
 min(purchase_date) AS first_date,max(purchase_date) AS last_date
 FROM {{ ref('int_synerise_purchase_dates') }} GROUP BY client_id
) d USING(client_id)
WHERE r.distinct_purchase_dates!=d.dates OR r.active_purchase_months!=d.months
 OR r.first_purchase_date!=d.first_date OR r.last_purchase_date!=d.last_date
 OR r.is_repeat_purchaser!=(d.dates>=2)
 OR (d.dates=1 AND isNotNull(r.days_to_second_purchase_date))
 OR (d.dates>=2 AND (isNull(r.days_to_second_purchase_date) OR r.days_to_second_purchase_date<=0))
