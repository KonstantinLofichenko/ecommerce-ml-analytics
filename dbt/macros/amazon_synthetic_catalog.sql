{% macro amazon_synthetic_candidates(input_relation=none) %}
-- Shared classification policy. No Synerise/Amazon identity match is inferred.
WITH input_catalog AS (
    {% if input_relation is not none %}
    SELECT * FROM {{ input_relation }}
    {% else %}
    SELECT
        a.parent_asin, a.product_name, a.source_department, a.main_category,
        r.categories
    FROM {{ ref('stg_amazon_products') }} AS a
    INNER JOIN {{ source('amazon', 'amazon_products') }} AS r
        ON a.parent_asin = r.parent_asin
    {% endif %}
), cleaned AS (
    SELECT *,
        arrayMap(x -> trimBoth(ifNull(x, '')), categories) AS clean_path,
        trimBoth(main_category) AS clean_main,
        if(source_department = 'All_Beauty', 'Beauty & Personal Care', 'Electronics')
            AS department_label
    FROM input_catalog
), validity AS (
    SELECT *,
        source_department IN ('All_Beauty', 'Electronics') AS known_department,
        length(clean_path) > 0 AS has_path,
        arrayAll(x -> x != '' AND lowerUTF8(x) NOT IN
            ('null', 'unknown', 'n/a', '(not set)'), clean_path) AS complete_path,
        if(source_department = 'All_Beauty',
            clean_path[1] IN ('Beauty & Personal Care', 'All Beauty', 'Premium Beauty'),
            clean_path[1] IN ('Electronics', 'Car & Vehicle Electronics')) AS compatible_root,
        if(source_department = 'All_Beauty',
            clean_main IN ('All Beauty', 'Premium Beauty', 'Beauty & Personal Care'),
            clean_main IN ('All Electronics', 'Electronics', 'Computers', 'Camera & Photo',
                'Cell Phones & Accessories', 'Home Audio & Theater', 'Car Electronics',
                'GPS & Navigation', 'Portable Audio & Accessories', 'Amazon Devices',
                'Apple Products')) AS compatible_main
    FROM cleaned
), classified AS (
    SELECT *,
        multiIf(
            trimBoth(product_name) = '' OR trimBoth(parent_asin) = '', 'excluded_empty_identity_or_title',
            NOT known_department, 'excluded_unknown_department',
            has_path AND NOT compatible_root, 'excluded_conflicting_hierarchy',
            has_path AND complete_path AND compatible_root AND clean_main = '', 'hierarchy_main_missing',
            has_path AND complete_path AND compatible_root AND NOT compatible_main, 'hierarchy_main_conflict',
            has_path AND complete_path AND compatible_root, 'hierarchy',
            compatible_main AND has_path, 'main_fallback_invalid_hierarchy',
            compatible_main, 'main_fallback_missing_hierarchy',
            'excluded_unclassified'
        ) AS classification_status,
        if(has_path AND complete_path AND compatible_root,
            clean_path,
            if(clean_main = department_label, [department_label], [department_label, clean_main]))
            AS synthetic_category_path
    FROM validity
)
SELECT
    parent_asin, product_name, source_department, main_category,
    classification_status, synthetic_category_path,
    toUInt8(classification_status = 'hierarchy_main_conflict') AS main_category_conflict,
    toJSONString(tuple(source_department, synthetic_category_path)) AS amazon_category_key
FROM classified
{% endmacro %}

{% macro amazon_synthetic_pool() %}
WITH candidates AS ({{ amazon_synthetic_candidates() }})
SELECT parent_asin, amazon_category_key, source_department,
    classification_status, main_category_conflict,
    cityHash64(amazon_category_key) AS amazon_category_index,
    row_number() OVER (ORDER BY parent_asin) AS catalog_index,
    row_number() OVER (PARTITION BY amazon_category_key ORDER BY parent_asin) AS category_product_index,
    count() OVER (PARTITION BY amazon_category_key) AS category_product_count,
    count() OVER () AS catalog_product_count
FROM candidates
WHERE NOT startsWith(classification_status, 'excluded_')
{% endmacro %}
