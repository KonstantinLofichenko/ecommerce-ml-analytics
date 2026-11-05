-- Final validated: Compare all five raw count features for a deterministic 32-customer sample.
-- Recovered from: compiled dbt test v4_raw_sample_reconciliation.sql.
-- Independent raw reconciliation for a deterministic bounded customer sample.
WITH eligible AS (
    SELECT *
      FROM (
        SELECT f.client_id AS client_id,
    parseDateTimeBestEffort(f.first_purchase_at, 'UTC') AS first_purchase_ts,
    f.cohort_month AS first_purchase_month,
    toUInt8(coalesce(r.days_to_second_purchase_date BETWEEN 1 AND 30, false)) AS target_30d
          FROM `synerise_analytics`.`int_synerise_customer_first_purchase` AS f
         INNER JOIN `synerise_analytics`.`fct_synerise_customer_repeat_purchase` AS r
         ON f.client_id = r.client_id
         WHERE first_purchase_ts >= toDateTime('2022-07-23 00:12:25', 'UTC')
           AND first_purchase_ts < toDateTime('2022-11-08 00:00:00', 'UTC')
)
    ORDER BY client_id
     LIMIT 32
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



), expected AS (
    SELECT e.client_id AS client_id,
        countIf(event_type='page_visit') AS page_views_30d,
        uniqExactIf(page_id,event_type='page_visit') AS unique_pages_30d,
        countIf(event_type='add_to_cart') AS cart_adds_30d,
        countIf(event_type='remove_from_cart') AS cart_removals_30d,
        countIf(event_type='search_query') AS searches_30d
      FROM events e
     INNER JOIN eligible p
     ON e.client_id=p.client_id
     WHERE e.client_id IN (
        SELECT client_id
          FROM eligible)
       AND event_ts>=p.first_purchase_ts-INTERVAL 30 DAY
       AND event_ts<p.first_purchase_ts
    GROUP BY e.client_id
)
SELECT m.client_id
  FROM `synerise_analytics`.`ml_customer_features` m
 INNER JOIN eligible p
 ON m.client_id=p.client_id
 LEFT JOIN expected e
 ON m.client_id=e.client_id
 WHERE
 m.page_views_30d!=coalesce(e.page_views_30d,0)
    OR

 m.unique_pages_30d!=coalesce(e.unique_pages_30d,0)
    OR

 m.cart_adds_30d!=coalesce(e.cart_adds_30d,0)
    OR

 m.cart_removals_30d!=coalesce(e.cart_removals_30d,0)
    OR

 m.searches_30d!=coalesce(e.searches_30d,0);
