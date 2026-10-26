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
, sessions AS (
  SELECT visitor, session_id, COUNT(*) AS events, COUNT(DISTINCT DATE(ts)) AS days
  FROM normalized WHERE visitor IS NOT NULL AND session_id IS NOT NULL
  GROUP BY visitor, session_id
), users AS (
  SELECT visitor, COUNT(*) AS sessions FROM sessions GROUP BY visitor
), shared_ids AS (
  SELECT session_id, COUNT(*) AS users FROM sessions GROUP BY session_id
), ties AS (
  SELECT visitor, session_id, ts, COUNT(*) AS n, COUNT(DISTINCT event_name) AS kinds
  FROM normalized WHERE visitor IS NOT NULL AND session_id IS NOT NULL AND ts IS NOT NULL
  GROUP BY visitor, session_id, ts HAVING COUNT(*) > 1
), links AS (
  SELECT visitor, COUNT(DISTINCT user_id) AS user_ids
  FROM normalized WHERE visitor IS NOT NULL AND user_id IS NOT NULL
    AND LOWER(TRIM(user_id)) NOT IN ('', '<other>', 'null', '(not set)') GROUP BY visitor
)
SELECT (SELECT COUNT(*) FROM sessions) AS composite_sessions,
  (SELECT COUNTIF(days > 1) FROM sessions) AS cross_midnight_sessions,
  (SELECT COUNTIF(sessions > 1) FROM users) AS visitors_with_multiple_sessions,
  (SELECT COUNTIF(users > 1) FROM shared_ids) AS session_ids_shared_across_visitors,
  (SELECT COUNT(*) FROM ties) AS timestamp_tie_groups,
  (SELECT SUM(n) FROM ties) AS events_in_ties,
  (SELECT COUNTIF(kinds > 1) FROM ties) AS mixed_name_ties,
  (SELECT COUNTIF(user_ids > 1) FROM links) AS pseudo_ids_with_multiple_user_ids;
