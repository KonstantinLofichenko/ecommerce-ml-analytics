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
SELECT COUNT(*) AS events,
  COUNTIF(user_pseudo_id IS NULL) AS null_pseudo,
  COUNTIF(user_pseudo_id IS NOT NULL AND TRIM(user_pseudo_id) = '') AS blank_pseudo,
  COUNTIF(user_pseudo_id IS NOT NULL AND TRIM(user_pseudo_id) != '' AND visitor IS NULL)
    AS known_placeholder_pseudo,
  COUNTIF(user_id IS NULL) AS null_user_id,
  COUNTIF(user_id IS NOT NULL AND LOWER(TRIM(user_id)) IN
          ('', '<other>', 'null', '(not set)')) AS unusable_nonnull_user_id,
  COUNT(DISTINCT user_id) AS raw_user_ids,
  COUNTIF(ARRAY_LENGTH(session_values) = 0) AS missing_integer_session_parameter,
  COUNTIF(ARRAY_LENGTH(session_values) > 1) AS repeated_integer_session_parameter,
  COUNTIF(session_id IS NULL) AS unusable_session_events,
  COUNTIF(visitor IS NULL OR session_id IS NULL) AS excluded_session_events
FROM normalized;
