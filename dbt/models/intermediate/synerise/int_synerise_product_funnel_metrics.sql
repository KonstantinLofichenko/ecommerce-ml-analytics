{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['sku']
    )
}}
-- depends_on: {{ ref('stg_synerise_add_to_cart') }}
-- depends_on: {{ ref('stg_synerise_product_buy') }}
-- depends_on: {{ ref('stg_synerise_product_properties') }}
-- Default builds recompute the original all-time metrics from raw staging events.
-- The explicitly requested one-time migration may reuse the validated existing fact.
{% if var('synerise_funnel_bootstrap', false) %}
SELECT sku, cart_customers, purchase_customers, conversion_rate
FROM {{ target.schema }}.fct_synerise_funnel_by_product
{% else %}
{{ synerise_product_funnel_metrics(ref('stg_synerise_add_to_cart'), ref('stg_synerise_product_buy'), ref('stg_synerise_product_properties')) }}
{% endif %}
