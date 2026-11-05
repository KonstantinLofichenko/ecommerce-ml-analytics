{{ config(tags=['customer_features_v4']) }}
-- Independent raw reconciliation for a deterministic bounded customer sample.
WITH eligible AS (
    SELECT * FROM ({{ customer_features_population() }}) ORDER BY client_id LIMIT 32
), events AS (
    {{ customer_features_events() }}
), expected AS (
    SELECT e.client_id AS client_id,
        countIf(event_type='page_visit') AS page_views_30d,
        uniqExactIf(page_id,event_type='page_visit') AS unique_pages_30d,
        countIf(event_type='add_to_cart') AS cart_adds_30d,
        countIf(event_type='remove_from_cart') AS cart_removals_30d,
        countIf(event_type='search_query') AS searches_30d
    FROM events e INNER JOIN eligible p ON e.client_id=p.client_id
    WHERE e.client_id IN (SELECT client_id FROM eligible)
      AND event_ts>=p.first_purchase_ts-INTERVAL 30 DAY AND event_ts<p.first_purchase_ts
    GROUP BY e.client_id
)
SELECT m.client_id FROM {{ ref('ml_customer_features') }} m
INNER JOIN eligible p ON m.client_id=p.client_id
LEFT JOIN expected e ON m.client_id=e.client_id
WHERE {% for col in ['page_views_30d','unique_pages_30d','cart_adds_30d','cart_removals_30d','searches_30d'] %}
 m.{{ col }}!=coalesce(e.{{ col }},0) {% if not loop.last %}OR{% endif %}
{% endfor %}
