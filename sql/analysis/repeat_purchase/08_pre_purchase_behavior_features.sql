-- Final validated: Derive raw-preserving strict-lookback features for active eligible customers.
-- Recovered from: compiled int_customer_behavior_30d.sql.
-- Expensive optional SELECT. Use the documented grace_hash join session settings; no table writes.
WITH eligible AS (
    SELECT f.client_id AS client_id,
    parseDateTimeBestEffort(f.first_purchase_at, 'UTC') AS first_purchase_ts,
    f.cohort_month AS first_purchase_month,
    toUInt8(coalesce(r.days_to_second_purchase_date BETWEEN 1 AND 30, false)) AS target_30d
      FROM `synerise_analytics`.`int_synerise_customer_first_purchase` AS f
     INNER JOIN `synerise_analytics`.`fct_synerise_customer_repeat_purchase` AS r
     ON f.client_id = r.client_id
     WHERE first_purchase_ts >= toDateTime('2022-07-23 00:12:25', 'UTC')
       AND first_purchase_ts < toDateTime('2022-11-08 00:00:00', 'UTC')

), events AS (
    SELECT client_id,
    parseDateTimeBestEffort(timestamp, 'UTC') AS event_ts,
    'page_visit' AS event_type,
    url AS page_id
      FROM `synerise_raw`.`page_visit`
    UNION ALL
    SELECT client_id,
    parseDateTimeBestEffort(timestamp, 'UTC') AS event_ts,
    'add_to_cart' AS event_type,
    toInt64(0) AS page_id
      FROM `synerise_raw`.`add_to_cart`
    UNION ALL
    SELECT client_id,
    parseDateTimeBestEffort(timestamp, 'UTC') AS event_ts,
    'remove_from_cart' AS event_type,
    toInt64(0) AS page_id
      FROM `synerise_raw`.`remove_from_cart`
    UNION ALL
    SELECT client_id,
    parseDateTimeBestEffort(timestamp, 'UTC') AS event_ts,
    'search_query' AS event_type,
    toInt64(0) AS page_id
      FROM `synerise_raw`.`search_query`



)
SELECT e.client_id AS client_id,
    countIf(e.event_type = 'page_visit') AS page_views_30d,
    uniqExactIf(e.page_id, e.event_type = 'page_visit') AS unique_pages_30d,
    countIf(e.event_type = 'add_to_cart') AS cart_adds_30d,
    countIf(e.event_type = 'remove_from_cart') AS cart_removals_30d,
    countIf(e.event_type = 'search_query') AS searches_30d,
    toUInt8(cart_adds_30d > 0) AS has_cart_activity_30d,
    toUInt8(count() > 0) AS has_behavioral_activity_30d,
    -- Audit-only columns, not predictive inputs.
    min(e.event_ts) AS first_behavior_ts,
    max(e.event_ts) AS last_behavior_ts
  FROM events AS e
 INNER JOIN eligible AS p
 ON e.client_id = p.client_id
 WHERE e.event_ts >= p.first_purchase_ts - INTERVAL 30 DAY
   AND e.event_ts < p.first_purchase_ts
GROUP BY e.client_id;
