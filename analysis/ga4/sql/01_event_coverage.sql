-- GoogleSQL. UNEXECUTED: no authorized local BigQuery access.
WITH extracted AS (
  SELECT _TABLE_SUFFIX AS source_day, event_date, event_name, event_timestamp,
    TIMESTAMP_MICROS(event_timestamp) AS ts, user_pseudo_id, user_id,
    ARRAY(SELECT p.value.int_value FROM UNNEST(event_params) p
          WHERE p.key = 'ga_session_id' AND p.value.int_value IS NOT NULL) AS session_values,
    ecommerce.transaction_id AS transaction_id,
    ecommerce.purchase_revenue AS purchase_revenue,
    ecommerce.refund_value AS refund_value,
    ARRAY_LENGTH(items) AS item_count
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
), normalized AS (
  SELECT *,
    IF(user_pseudo_id IS NULL OR LOWER(TRIM(user_pseudo_id)) IN
       ('', '<other>', 'null', '(not set)'), NULL, user_pseudo_id) AS visitor,
    IF(transaction_id IS NULL OR LOWER(TRIM(transaction_id)) IN
       ('', '<other>', 'null', '(not set)'), NULL, transaction_id) AS tx,
    IF(ARRAY_LENGTH(session_values) = 1 AND session_values[SAFE_OFFSET(0)] > 0,
       session_values[SAFE_OFFSET(0)], NULL) AS session_id
  FROM extracted
)
SELECT
  CASE WHEN GROUPING(source_day) = 0 THEN 'source_day'
       WHEN GROUPING(SUBSTR(source_day, 1, 6)) = 0 THEN 'source_month'
       ELSE 'all' END AS grain,
  source_day, SUBSTR(source_day, 1, 6) AS source_month, event_name,
  COUNT(*) AS events, COUNT(DISTINCT visitor) AS usable_visitors,
  COUNT(DISTINCT user_pseudo_id) AS raw_pseudo_ids,
  COUNTIF(visitor IS NOT NULL) AS identified_events,
  SAFE_DIVIDE(COUNTIF(visitor IS NOT NULL), COUNT(*)) AS identified_fraction,
  COUNTIF(visitor IS NOT NULL AND session_id IS NOT NULL) AS session_linkable_events,
  COUNTIF(ts IS NULL) AS missing_timestamps, MIN(ts) AS first_ts, MAX(ts) AS last_ts,
  COUNTIF(event_date != FORMAT_TIMESTAMP('%Y%m%d', ts, 'UTC')) AS property_date_differs_utc
FROM normalized
GROUP BY GROUPING SETS ((source_day, event_name),
  (SUBSTR(source_day, 1, 6), event_name), (event_name), ())
ORDER BY grain, source_day, source_month, event_name;
