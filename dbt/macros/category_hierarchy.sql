{% macro category_hierarchy(path) %}
{# Nonempty, nonblank paths are a source contract, verified before migration and by tests. #}
{% for level in range(1, 6) %}
arrayElement({{ path }}, least(toUInt64({{ level }}), length({{ path }}))) AS category_level_{{ level }},
{% endfor %}
length({{ path }}) AS category_depth,
arrayElement({{ path }}, -1) AS category_leaf
{% endmacro %}

{% macro inherited_category_hierarchy(alias) %}
{% for level in range(1, 6) %}
{{ alias }}.category_level_{{ level }} AS category_level_{{ level }},
{% endfor %}
{{ alias }}.category_depth AS category_depth,
{{ alias }}.category_leaf AS category_leaf
{% endmacro %}
