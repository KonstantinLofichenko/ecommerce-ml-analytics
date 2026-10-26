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
, purchases AS (
  SELECT * FROM normalized WHERE event_name = 'purchase'
), tx_quality AS (
  SELECT tx, COUNT(DISTINCT visitor) AS visitors,
    COUNTIF(visitor IS NULL) AS unidentified, COUNT(*) AS events,
    COUNT(DISTINCT purchase_revenue) AS revenue_values
  FROM purchases WHERE tx IS NOT NULL GROUP BY tx
), orders AS (
  -- Exploratory conservative scenario; retain raw purchase events in parallel.
  SELECT p.visitor, p.tx, MIN(p.ts) AS ts
  FROM purchases p JOIN tx_quality q USING (tx)
  WHERE p.visitor IS NOT NULL AND p.ts IS NOT NULL
    AND q.visitors = 1 AND q.unidentified = 0 AND q.revenue_values <= 1
  GROUP BY p.visitor, p.tx
)
, snapshots AS (
  SELECT snapshot FROM UNNEST([TIMESTAMP '2020-12-01 00:00:00+00',
    TIMESTAMP '2020-12-15 00:00:00+00', TIMESTAMP '2021-01-01 00:00:00+00',
    TIMESTAMP '2021-01-15 00:00:00+00']) snapshot
), scenarios AS (
  SELECT 'event_target' AS scenario, visitor, ts FROM purchases
    WHERE visitor IS NOT NULL AND ts IS NOT NULL
  UNION ALL SELECT 'candidate_order_target', visitor, ts FROM orders
), customer_labels AS (
  SELECT scenario, snapshot, visitor, MIN(ts) AS first_purchase,
    COUNTIF(ts < snapshot) AS prior_purchases,
    COUNTIF(ts >= snapshot AND ts < TIMESTAMP_ADD(snapshot, INTERVAL 14 DAY)) > 0 AS positive
  FROM scenarios CROSS JOIN snapshots GROUP BY scenario, snapshot, visitor
  HAVING COUNTIF(ts < snapshot) > 0
)
SELECT scenario, snapshot, COUNT(*) AS eligible_customers, COUNTIF(positive) AS positives,
  COUNTIF(NOT positive) AS negatives, SAFE_DIVIDE(COUNTIF(positive), COUNT(*)) AS positive_rate,
  MIN(prior_purchases) AS minimum_prior_purchases,
  TIMESTAMP_DIFF(snapshot, TIMESTAMP '2020-11-01 00:00:00+00', DAY) AS maximum_history_days,
  TIMESTAMP_ADD(snapshot, INTERVAL 14 DAY) AS label_end_exclusive,
  TIMESTAMP_ADD(snapshot, INTERVAL 14 DAY) <= TIMESTAMP '2021-02-01 00:00:00+00'
    AS nominal_full_window,
  COUNT(*) AS eligible_with_usable_pseudo_id,
  COUNTIF(first_purchase < TIMESTAMP '2020-12-01 00:00:00+00') AS overlap_with_first_snapshot
FROM customer_labels GROUP BY scenario, snapshot ORDER BY scenario, snapshot;
