{{
    config(
        tags=['synthetic_catalog']
    )
}}
WITH pool AS ({{ amazon_synthetic_pool() }}),
    candidates AS ({{ amazon_synthetic_candidates() }})
SELECT 'empty_or_ambiguous_catalog' AS issue
FROM pool
HAVING count() = 0 OR count() != uniqExact(parent_asin)
    OR uniqExact(amazon_category_key) != uniqExact(amazon_category_index)
UNION ALL
SELECT 'invalid_eligible_donor'
FROM candidates
WHERE NOT startsWith(classification_status, 'excluded_') AND (trimBoth(product_name) = '' OR trimBoth(parent_asin) = ''
    OR empty(synthetic_category_path)
    OR arrayExists(x -> trimBoth(x) = '', synthetic_category_path)
    OR startsWith(classification_status, 'excluded_')
    )

SETTINGS max_threads=1, max_block_size=8192, max_memory_usage=1073741824,
    max_bytes_before_external_sort=33554432, max_bytes_before_external_group_by=67108864,
    max_bytes_in_join=67108864, join_algorithm='grace_hash'
