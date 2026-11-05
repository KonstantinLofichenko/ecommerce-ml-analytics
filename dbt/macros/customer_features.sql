{% macro customer_features_population() %}
SELECT f.client_id AS client_id,
    parseDateTimeBestEffort(f.first_purchase_at, 'UTC') AS first_purchase_ts,
    f.cohort_month AS first_purchase_month,
    toUInt8(coalesce(r.days_to_second_purchase_date BETWEEN 1 AND 30, false)) AS target_30d
FROM {{ ref('int_synerise_customer_first_purchase') }} AS f
INNER JOIN {{ ref('fct_synerise_customer_repeat_purchase') }} AS r
    ON f.client_id = r.client_id
WHERE first_purchase_ts >= toDateTime('{{ var("v4_eligibility_start", "2022-07-23 00:12:25") }}', 'UTC')
  AND first_purchase_ts < toDateTime('{{ var("v4_eligibility_end", "2022-11-08 00:00:00") }}', 'UTC')
{% endmacro %}

{% macro customer_features_events() %}
{% for event in ['page_visit', 'add_to_cart', 'remove_from_cart', 'search_query'] %}
SELECT client_id,
    parseDateTimeBestEffort(timestamp, 'UTC') AS event_ts,
    '{{ event }}' AS event_type,
    {% if event == 'page_visit' %}url{% else %}toInt64(0){% endif %} AS page_id
FROM {{ source('synerise', event) }}
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}
{% endmacro %}
