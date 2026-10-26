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
, frequencies AS (
  SELECT visitor, COUNT(*) AS orders FROM orders GROUP BY visitor
), event_frequencies AS (
  SELECT visitor, COUNT(*) AS purchases FROM purchases
  WHERE visitor IS NOT NULL GROUP BY visitor
), gaps AS (
  SELECT TIMESTAMP_DIFF(ts, LAG(ts) OVER (PARTITION BY visitor ORDER BY ts, tx), MICROSECOND)
    / 86400000000.0 AS days FROM orders
)
SELECT (SELECT COUNT(*) FROM purchases) AS purchase_events,
  (SELECT COUNT(DISTINCT visitor) FROM purchases) AS purchasing_visitors,
  (SELECT COUNT(DISTINCT tx) FROM purchases) AS distinct_usable_transaction_ids,
  (SELECT COUNTIF(tx IS NULL) FROM purchases) AS unusable_transaction_events,
  (SELECT COUNTIF(events > 1) FROM tx_quality) AS repeated_transaction_ids,
  (SELECT COUNTIF(visitors > 1 OR unidentified > 0) FROM tx_quality) AS ambiguous_identity_ids,
  (SELECT COUNTIF(revenue_values > 1) FROM tx_quality) AS conflicting_revenue_ids,
  (SELECT COUNTIF(purchase_revenue < 0) FROM purchases) AS negative_purchase_revenue,
  (SELECT COUNTIF(purchase_revenue IS NULL) FROM purchases) AS missing_purchase_revenue,
  (SELECT COUNTIF(event_name = 'refund') FROM normalized) AS refund_events,
  (SELECT COUNT(*) FROM orders) AS candidate_orders,
  (SELECT COUNTIF(orders >= 2) FROM frequencies) AS repeat_order_visitors,
  (SELECT COUNTIF(days = 0) FROM gaps) AS tied_order_times,
  (SELECT APPROX_QUANTILES(days, 100) FROM gaps WHERE days IS NOT NULL) AS gap_day_percentiles,
  ARRAY(SELECT AS STRUCT purchases, COUNT(*) AS visitors FROM event_frequencies
        GROUP BY purchases ORDER BY purchases) AS purchase_events_per_visitor,
  ARRAY(SELECT AS STRUCT orders, COUNT(*) AS visitors FROM frequencies GROUP BY orders
        ORDER BY orders) AS orders_per_visitor,
  ARRAY(SELECT AS STRUCT FORMAT_TIMESTAMP('%Y-%m', ts) AS utc_month,
        COUNT(*) AS events, COUNT(DISTINCT visitor) AS visitors
        FROM purchases GROUP BY utc_month ORDER BY utc_month) AS monthly_purchases;
