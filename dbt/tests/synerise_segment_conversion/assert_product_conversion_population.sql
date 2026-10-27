SELECT coalesce(c.sku,t.sku) AS id
FROM {{ ref('int_synerise_product_first_cart') }} c
FULL OUTER JOIN {{ ref('int_synerise_product_conversion_times') }} t
    ON c.sku=t.sku AND c.client_id=t.client_id
WHERE c.client_id IS NULL OR t.client_id IS NULL OR c.first_cart_time!=t.first_cart_time
SETTINGS join_use_nulls=1, join_algorithm='grace_hash', max_bytes_in_join=67108864,
    max_threads=1, max_memory_usage=1073741824, max_block_size=8192
