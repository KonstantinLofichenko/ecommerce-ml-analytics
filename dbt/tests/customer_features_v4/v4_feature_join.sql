{{ config(tags=['customer_features_v4']) }}
SELECT m.client_id FROM {{ ref('ml_customer_features') }} m
LEFT JOIN {{ ref('int_customer_behavior_30d') }} b USING(client_id)
WHERE {% for col in ['page_views_30d','unique_pages_30d','cart_adds_30d','cart_removals_30d','searches_30d','has_cart_activity_30d','has_behavioral_activity_30d'] %}
 m.{{ col }}!=coalesce(b.{{ col }},0) {% if not loop.last %}OR{% endif %}
{% endfor %}
