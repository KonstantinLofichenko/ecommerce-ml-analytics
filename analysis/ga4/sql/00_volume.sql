-- GoogleSQL. UNEXECUTED: no authorized local BigQuery access.
SELECT table_id, row_count, size_bytes
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.__TABLES__`
WHERE table_id BETWEEN CONCAT('events_', @start_suffix) AND CONCAT('events_', @end_suffix)
ORDER BY table_id;
