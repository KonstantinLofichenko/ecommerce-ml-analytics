{% for grain, relation, key in [
    ('customer', 'fct_synerise_time_to_conversion', 'metric_scope'),
    ('category', 'fct_synerise_time_to_conversion_by_category', 'category_id'),
    ('product', 'fct_synerise_time_to_conversion_by_product', 'sku')
] %}
SELECT '{{ grain }}' AS grain, toString({{ key }}) AS id
FROM {{ ref(relation) }}
WHERE NOT (converted_1h <= converted_24h AND converted_24h <= converted_7d
    AND converted_7d <= eligible_customers_7d)
    OR toInt64(converted_1h)<0
    OR toInt64(converted_1h)
       + (toInt64(converted_24h)-toInt64(converted_1h))
       + (toInt64(converted_7d)-toInt64(converted_24h))
       + (toInt64(eligible_customers_7d)-toInt64(converted_7d)) != eligible_customers_7d
    OR (eligible_customers_7d>0 AND abs(
       toFloat64(converted_1h)/eligible_customers_7d
       + toFloat64(toInt64(converted_24h)-toInt64(converted_1h))/eligible_customers_7d
       + toFloat64(toInt64(converted_7d)-toInt64(converted_24h))/eligible_customers_7d
       + toFloat64(toInt64(eligible_customers_7d)-toInt64(converted_7d))/eligible_customers_7d - 1)>1e-12)
    OR (eligible_customers_7d=0 AND isNotNull(toFloat64(converted_7d)/nullIf(eligible_customers_7d,0)))
    OR (converted_7d=0 AND isNotNull(toFloat64(converted_1h)/nullIf(converted_7d,0)))
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}
