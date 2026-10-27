{% macro synerise_segment_summary(relation, key) %}
SELECT {{ key }}, count() AS cart_customers,
    countIf(converted=1) AS converted_customers,
    if(converted_customers=0, NULL, avgIf(seconds_to_conversion, converted=1)) AS avg_seconds,
{% for q, name in [(0.50, 'p50'), (0.75, 'p75'), (0.90, 'p90')] %}
    if(converted_customers=0, NULL, quantileExactIf({{ q }})(seconds_to_conversion, converted=1)) AS {{ name }}_seconds,
{% endfor %}
    countIf(first_cart_time <= toDateTime('2022-12-08 00:09:59') - INTERVAL 7 DAY) AS eligible_customers_7d,
{% for seconds, name in [(3600, '1h'), (86400, '24h'), (604800, '7d')] %}
    countIf(first_cart_time <= toDateTime('2022-12-08 00:09:59') - INTERVAL 7 DAY
        AND converted=1 AND seconds_to_conversion <= {{ seconds }}) AS converted_{{ name }},
    toFloat64(converted_{{ name }}) / nullIf(eligible_customers_7d, 0) AS conversion_{{ name }}_rate{% if not loop.last %},{% endif %}
{% endfor %}
FROM {{ relation }}
GROUP BY {{ key }}
{% endmacro %}
