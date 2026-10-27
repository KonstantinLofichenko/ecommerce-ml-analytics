{% test unique_in_order(model, column_name) %}

SELECT
    {{ column_name }}
FROM {{ model }}
GROUP BY {{ column_name }}
HAVING count() > 1

SETTINGS
    max_threads = 1,
    optimize_aggregation_in_order = 1,
    max_memory_usage = 1073741824

{% endtest %}