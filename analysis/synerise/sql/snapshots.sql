WITH variants AS (
  SELECT 'A_event' AS definition,client_id,ts FROM product_buy
  UNION ALL SELECT 'B_timestamp_occasion',client_id,ts FROM product_buy GROUP BY client_id,ts
  UNION ALL SELECT 'C_purchase_day',client_id,CAST(CAST(ts AS DATE) AS TIMESTAMP)
    FROM product_buy GROUP BY client_id,CAST(ts AS DATE)
), labels AS (
  SELECT definition,snapshot,client_id,count_if(ts<snapshot) AS prior,
    count_if(ts>=snapshot AND ts<snapshot+INTERVAL 14 DAY)>0 AS positive
  FROM variants CROSS JOIN snapshots
  WHERE client_id IS NOT NULL AND ts IS NOT NULL GROUP BY ALL HAVING count_if(ts<snapshot)>0
)
SELECT definition,snapshot,count(*) AS eligible,count_if(positive) AS positives,
  count_if(NOT positive) AS negatives,avg(positive::INT) AS positive_rate,
  min(prior) AS minimum_prior,
  (SELECT min(ts) FROM events) AS source_start,
  snapshot+INTERVAL 14 DAY AS label_end_exclusive,
  snapshot+INTERVAL 14 DAY <= (SELECT max(ts) FROM events) AS full_followup
FROM labels GROUP BY definition,snapshot ORDER BY definition,snapshot;
