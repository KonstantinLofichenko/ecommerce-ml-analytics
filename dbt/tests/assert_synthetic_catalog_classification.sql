{{
    config(
        tags=['synthetic_catalog']
    )
}}
-- Small adversarial fixtures validate preference, explicit fallback and exclusion.
WITH fixtures AS (
    SELECT 'hierarchy' AS parent_asin, 'Cable' AS product_name,
        'Electronics' AS source_department, 'Computers' AS main_category,
        ['Electronics', 'Computers & Accessories', 'USB Cables'] AS categories
    UNION ALL SELECT 'conflict', 'Cable', 'Electronics', 'All Beauty', ['Electronics', 'USB Cables']
    UNION ALL SELECT 'missing', 'Shampoo', 'All_Beauty', 'All Beauty', []
    UNION ALL SELECT 'bad_root', 'Cable', 'Electronics', 'Computers', ['Books', 'Fiction']
    UNION ALL SELECT 'bad_path', 'Cable', 'Electronics', 'Computers', ['Electronics', '']
    UNION ALL SELECT 'missing_all', 'Cable', 'Electronics', '', []
    UNION ALL SELECT 'empty_title', '  ', 'Electronics', 'Computers', []
    UNION ALL SELECT 'unknown_department', 'Cable', 'Other', 'Computers', []
    UNION ALL SELECT 'main_missing', 'Cable', 'Electronics', '', ['Electronics', 'USB Cables']
), classified AS ({{ amazon_synthetic_candidates('fixtures') }})
SELECT parent_asin, classification_status
FROM classified
WHERE classification_status != multiIf(
    parent_asin = 'hierarchy', 'hierarchy',
    parent_asin = 'conflict', 'hierarchy_main_conflict',
    parent_asin = 'missing', 'main_fallback_missing_hierarchy',
    parent_asin = 'bad_root', 'excluded_conflicting_hierarchy',
    parent_asin = 'bad_path', 'main_fallback_invalid_hierarchy',
    parent_asin = 'missing_all', 'excluded_unclassified',
    parent_asin = 'empty_title', 'excluded_empty_identity_or_title',
    parent_asin = 'unknown_department', 'excluded_unknown_department',
    'hierarchy_main_missing')
    OR (parent_asin = 'conflict' AND main_category_conflict != 1)
    OR (parent_asin = 'missing' AND synthetic_category_path != ['Beauty & Personal Care', 'All Beauty'])
    OR (parent_asin = 'hierarchy' AND synthetic_category_path != ['Electronics', 'Computers & Accessories', 'USB Cables'])
