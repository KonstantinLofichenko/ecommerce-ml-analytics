-- Final validated: Return missing anchors or contributing event extrema outside the strict lookback.
-- Recovered from: compiled dbt test v4_window_audit.sql.
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
)
SELECT b.client_id
  FROM `synerise_analytics`.`int_customer_behavior_30d` b
 LEFT JOIN eligible p
 USING(client_id)
 WHERE p.client_id IS NULL
    OR b.first_behavior_ts<p.first_purchase_ts-INTERVAL 30 DAY
    OR b.last_behavior_ts>=p.first_purchase_ts
    OR b.first_behavior_ts>b.last_behavior_ts
 SETTINGS join_use_nulls=1;
