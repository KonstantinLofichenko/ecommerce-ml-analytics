{% macro synerise_product_funnel_metrics(cart_relation, purchase_relation, properties_relation=none) %}
WITH customer_product_events AS (

    SELECT
        client_id,
        sku,
        minIf(event_time_source, event_type = 'cart') AS first_cart_time,
        countIf(event_type = 'cart') AS cart_events,
        maxIf(event_time_source, event_type = 'purchase') AS last_purchase_time,
        countIf(event_type = 'purchase') AS purchase_events

    FROM (

        SELECT
            client_id,
            sku,
            event_time_source,
            'cart' AS event_type
        FROM {{ cart_relation }}

        UNION ALL

        SELECT
            client_id,
            sku,
            event_time_source,
            'purchase' AS event_type
        FROM {{ purchase_relation }}

    )

    GROUP BY client_id, sku

),

funnel AS (

    SELECT
        sku,
        countIf(cart_events > 0) AS cart_customers,
        countIf(
            cart_events > 0
            AND purchase_events > 0
            AND last_purchase_time >= first_cart_time
        ) AS purchase_customers

    FROM customer_product_events
    GROUP BY sku

)

SELECT sku, cart_customers, purchase_customers,
    toFloat64(purchase_customers) / nullIf(cart_customers, 0) AS conversion_rate
FROM funnel WHERE cart_customers > 0

{% endmacro %}

{% macro synerise_category_funnel_metrics(cart_relation, purchase_relation, properties_relation=none) %}
WITH cart_events AS (
    SELECT
        c.client_id,
        p.category_id,
        c.event_time_source
    FROM {{ cart_relation }} AS c
    INNER JOIN {{ properties_relation }} AS p
        ON c.sku = p.sku
)

,first_cart AS (
    SELECT
        client_id,
        category_id,
        min(event_time_source) AS first_cart_time
    FROM cart_events
    GROUP BY client_id, category_id
)

,purchase_events AS (
    SELECT
        b.client_id,
        p.category_id,
        b.event_time_source
    FROM {{ purchase_relation }} AS b
    INNER JOIN {{ properties_relation }} AS p
        ON b.sku = p.sku
)

,converted AS (
    SELECT
        c.client_id,
        c.category_id,
        toUInt8(1) AS converted
    FROM first_cart AS c
    INNER JOIN purchase_events AS p
        ON c.client_id = p.client_id
       AND c.category_id = p.category_id
    WHERE p.event_time_source >= c.first_cart_time
    GROUP BY c.client_id, c.category_id
)

,funnel_metrics AS (
    SELECT
        c.category_id,
        count() AS cart_customers,
        countIf(p.converted = 1) AS purchase_customers,
        toFloat64(purchase_customers)
            / nullIf(cart_customers, 0) AS conversion_rate
    FROM first_cart AS c
    LEFT JOIN converted AS p
        ON c.client_id = p.client_id
       AND c.category_id = p.category_id
    GROUP BY c.category_id
)

SELECT category_id, cart_customers, purchase_customers, conversion_rate FROM funnel_metrics

{% endmacro %}
