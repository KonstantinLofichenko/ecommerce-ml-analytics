-- Exact streaming uniqueness check over the MergeTree sorting key.
SELECT client_id
FROM {{ ref('int_synerise_customer_conversion_times') }}
GROUP BY client_id
HAVING count() > 1
SETTINGS optimize_aggregation_in_order = 1,
    max_threads = 1,
    max_memory_usage = 1073741824
