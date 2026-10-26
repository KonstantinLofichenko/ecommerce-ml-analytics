{% test category_hierarchy_valid(model) %}
SELECT category_id FROM {{ model }}
WHERE empty(synthetic_category_path)
    OR arrayExists(x -> isNull(x) OR trimBoth(ifNull(x, '')) = '', synthetic_category_path)
    OR category_depth != length(synthetic_category_path)
    OR category_depth NOT BETWEEN 2 AND 7
    OR category_leaf != arrayElement(synthetic_category_path, -1)
    OR toTypeName(category_leaf) != 'String'
{% for level in range(1, 6) %}
    OR category_level_{{ level }} != arrayElement(synthetic_category_path, least(toUInt64({{ level }}), length(synthetic_category_path)))
    OR category_level_{{ level }} = ''
    OR toTypeName(category_level_{{ level }}) != 'String'
{% endfor %}
{% endtest %}
