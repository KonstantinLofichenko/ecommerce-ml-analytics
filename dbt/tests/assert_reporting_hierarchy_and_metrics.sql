-- Narrow aggregates are the canonical metric layer; enrichment cannot change the grain.
{% for grain, key in [('product', 'sku'), ('category', 'category_id')] %}
SELECT '{{ grain }}' AS grain, toString(f.{{ key }}) AS id
FROM {{ ref('fct_synerise_funnel_by_' ~ grain) }} f
FULL OUTER JOIN {{ ref('int_synerise_' ~ grain ~ '_funnel_metrics') }} m
    ON f.{{ key }} = m.{{ key }}
WHERE f.{{ key }} IS NULL OR m.{{ key }} IS NULL OR f.{{ key }} != m.{{ key }} OR f.cart_customers != m.cart_customers
    OR f.purchase_customers != m.purchase_customers
    OR ifNull(f.conversion_rate, -1) != ifNull(m.conversion_rate, -1)
    OR f.purchase_customers > f.cart_customers
    OR ifNull(f.conversion_rate, -1) != ifNull(toFloat64(f.purchase_customers) / nullIf(f.cart_customers, 0), -1)
UNION ALL
SELECT '{{ grain }} hierarchy' AS grain, toString(f.{{ key }}) AS id
FROM {{ ref('fct_synerise_funnel_by_' ~ grain) }} f
LEFT JOIN {{ ref('dim_synerise_categories') }} d ON f.category_id = d.category_id
WHERE f.synthetic_category_path != d.synthetic_category_path
    OR f.category_depth != d.category_depth OR f.category_leaf != d.category_leaf
{% for level in range(1, 6) %}
    OR f.category_level_{{ level }} != d.category_level_{{ level }}
{% endfor %}
{% if not loop.last %} UNION ALL {% endif %}
{% endfor %}

SETTINGS join_use_nulls=1, max_threads=1, max_memory_usage=1073741824,
    join_algorithm='grace_hash', max_bytes_in_join=67108864
