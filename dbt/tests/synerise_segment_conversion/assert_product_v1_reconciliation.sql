SELECT coalesce(a.sku,b.sku) AS id
FROM {{ ref('fct_synerise_time_to_conversion_by_product') }} a
FULL OUTER JOIN {{ ref('fct_synerise_funnel_by_product') }} b ON a.sku=b.sku
WHERE a.sku IS NULL OR b.sku IS NULL OR a.cart_customers!=b.cart_customers
    OR a.converted_customers!=b.purchase_customers
SETTINGS join_use_nulls=1, join_algorithm='grace_hash', max_bytes_in_join=67108864,
    max_threads=1, max_memory_usage=1073741824, max_block_size=8192
