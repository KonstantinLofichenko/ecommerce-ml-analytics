-- GoogleSQL. UNEXECUTED: no authorized local BigQuery access.
-- Run first: actual historical fields, not assumptions from today's export schema.
SELECT table_name, column_name, data_type, is_nullable
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name BETWEEN CONCAT('events_', @start_suffix) AND CONCAT('events_', @end_suffix)
ORDER BY table_name, ordinal_position;
