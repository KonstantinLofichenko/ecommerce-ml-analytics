SELECT coalesce(c.category_id,t.category_id) AS id
FROM {{ ref('int_synerise_category_first_cart') }} c
FULL OUTER JOIN {{ ref('int_synerise_category_conversion_times') }} t
    ON c.category_id=t.category_id AND c.client_id=t.client_id
WHERE c.client_id IS NULL OR t.client_id IS NULL OR c.first_cart_time!=t.first_cart_time
SETTINGS join_use_nulls=1, join_algorithm='grace_hash', max_bytes_in_join=67108864,
    max_threads=1, max_memory_usage=1073741824, max_block_size=8192
