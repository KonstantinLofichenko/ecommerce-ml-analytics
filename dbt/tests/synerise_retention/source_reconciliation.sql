{{ config(tags=['synerise_retention']) }}
SELECT 1 WHERE
 (SELECT count() FROM {{ ref('int_synerise_customer_first_purchase') }}) !=
 (SELECT uniqExact(client_id) FROM {{ source('synerise','product_buy') }})
 OR (SELECT count() FROM {{ ref('fct_synerise_customer_repeat_purchase') }}) !=
 (SELECT count() FROM {{ ref('int_synerise_customer_first_purchase') }})
 OR (SELECT countIf(NOT match(timestamp, '^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$')
 OR isNull(parseDateTimeBestEffortOrNull(timestamp))) FROM {{ source('synerise','product_buy') }}) != 0
