{% test catalog_unique(model, column_name) %}
-- Canonical tables are sorted by this identifier. In-order aggregation bounds memory
-- without maintaining an exact distinct hash set for every product.
SELECT {{ column_name }}
FROM {{ model }}
GROUP BY {{ column_name }}
HAVING count() > 1
SETTINGS optimize_aggregation_in_order=1, max_threads=1, max_block_size=8192,
    max_memory_usage=1073741824, max_bytes_before_external_group_by=67108864
{% endtest %}
