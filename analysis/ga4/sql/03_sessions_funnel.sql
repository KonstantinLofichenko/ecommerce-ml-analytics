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
, eligible AS (
  SELECT * FROM normalized WHERE visitor IS NOT NULL AND session_id IS NOT NULL
), s1 AS (
  SELECT visitor, session_id, MIN(ts) AS first_ts, MAX(ts) AS last_ts, COUNT(*) AS events,
    COUNT(DISTINCT DATE(ts, 'UTC')) AS utc_days,
    COUNTIF(event_name = 'page_view') > 0 AS p1,
    COUNTIF(event_name = 'view_item') > 0 AS p2,
    COUNTIF(event_name = 'add_to_cart') > 0 AS p3,
    COUNTIF(event_name = 'begin_checkout') > 0 AS p4,
    COUNTIF(event_name = 'purchase') > 0 AS p5,
    MIN(IF(event_name = 'page_view', ts, NULL)) AS t1
  FROM eligible GROUP BY visitor, session_id
), s2 AS (
  SELECT s1.*, MIN(e.ts) AS t2
  FROM s1 LEFT JOIN eligible e ON e.visitor = s1.visitor
    AND e.session_id = s1.session_id AND e.event_name = 'view_item'
    AND e.ts > s1.t1
  GROUP BY ALL
), s3 AS (
  SELECT s2.*, MIN(e.ts) AS t3
  FROM s2 LEFT JOIN eligible e ON e.visitor = s2.visitor
    AND e.session_id = s2.session_id AND e.event_name = 'add_to_cart'
    AND e.ts > s2.t2
  GROUP BY ALL
), s4 AS (
  SELECT s3.*, MIN(e.ts) AS t4
  FROM s3 LEFT JOIN eligible e ON e.visitor = s3.visitor
    AND e.session_id = s3.session_id AND e.event_name = 'begin_checkout'
    AND e.ts > s3.t3
  GROUP BY ALL
), s5 AS (
  SELECT s4.*, MIN(e.ts) AS t5
  FROM s4 LEFT JOIN eligible e ON e.visitor = s4.visitor
    AND e.session_id = s4.session_id AND e.event_name = 'purchase'
    AND e.ts > s4.t4
  GROUP BY ALL
)
SELECT COUNT(*) AS sessions, COUNTIF(utc_days > 1) AS cross_midnight_sessions,
  COUNTIF(p1) AS presence_page, COUNTIF(p1 AND p2) AS presence_item,
  COUNTIF(p1 AND p2 AND p3) AS presence_cart,
  COUNTIF(p1 AND p2 AND p3 AND p4) AS presence_checkout,
  COUNTIF(p1 AND p2 AND p3 AND p4 AND p5) AS presence_purchase,
  COUNTIF(t1 IS NOT NULL) AS strict_page, COUNTIF(t2 IS NOT NULL) AS strict_item,
  COUNTIF(t3 IS NOT NULL) AS strict_cart, COUNTIF(t4 IS NOT NULL) AS strict_checkout,
  COUNTIF(t5 IS NOT NULL) AS strict_purchase,
  COUNTIF(p5 AND NOT (p1 AND p2 AND p3 AND p4)) AS purchase_missing_required_steps
FROM s5;
