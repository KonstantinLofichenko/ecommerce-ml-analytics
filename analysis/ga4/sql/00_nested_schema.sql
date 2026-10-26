-- GoogleSQL. UNEXECUTED: no authorized local BigQuery access.
SELECT table_name, column_name, field_path, data_type
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
WHERE table_name BETWEEN CONCAT('events_', @start_suffix) AND CONCAT('events_', @end_suffix)
ORDER BY table_name, field_path;
