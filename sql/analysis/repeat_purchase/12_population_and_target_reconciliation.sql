-- Final validated: Return customer mismatches against the reused eligibility and calendar-date target.
-- Recovered from: compiled dbt test v4_population_and_target.sql.
WITH expected AS (
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
SELECT coalesce(e.client_id,m.client_id) AS client_id
  FROM expected e
 FULL OUTER JOIN `synerise_analytics`.`ml_customer_features` m
 USING(client_id)
 WHERE e.client_id IS NULL
    OR m.client_id IS NULL
    OR m.target_30d!=e.target_30d
    OR m.first_purchase_ts!=e.first_purchase_ts
    OR m.first_purchase_month!=e.first_purchase_month
 SETTINGS join_use_nulls=1;
