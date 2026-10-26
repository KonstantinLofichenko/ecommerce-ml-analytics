{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['category_id']
    )
}}
-- depends_on: {{ ref('stg_synerise_add_to_cart') }}
-- depends_on: {{ ref('stg_synerise_product_buy') }}
-- depends_on: {{ ref('stg_synerise_product_properties') }}
-- Default builds recompute the original all-time metrics from raw staging events.
-- The explicitly requested one-time migration may reuse the validated existing fact.
{% if var('synerise_funnel_bootstrap', false) %}
SELECT category_id, cart_customers, purchase_customers, conversion_rate
FROM {{ target.schema }}.fct_synerise_funnel_by_category
{% else %}
{{ synerise_category_funnel_metrics(ref('stg_synerise_add_to_cart'), ref('stg_synerise_product_buy'), ref('stg_synerise_product_properties')) }}
{% endif %}
SETTINGS max_threads=1, max_memory_usage=1073741824, max_block_size=8192,
    max_bytes_before_external_group_by=67108864, max_bytes_before_external_sort=33554432,
    max_insert_block_size=65536, min_insert_block_size_rows=65536,
    min_insert_block_size_bytes=16777216, join_algorithm='grace_hash',
    max_bytes_in_join=134217728