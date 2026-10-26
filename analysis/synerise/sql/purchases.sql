WITH variants AS (
  SELECT 'A_event' AS definition,client_id,ts,sku FROM product_buy
  UNION ALL SELECT 'B_timestamp_occasion',client_id,ts,NULL::BIGINT
    FROM product_buy GROUP BY client_id,ts
  UNION ALL SELECT 'C_purchase_day',client_id,CAST(CAST(ts AS DATE) AS TIMESTAMP),NULL::BIGINT
    FROM product_buy GROUP BY client_id,CAST(ts AS DATE)
), counts AS (
  SELECT definition,client_id,count(*) AS purchases,
    date_diff('day',min(ts),max(ts)) AS span_days
  FROM variants WHERE client_id IS NOT NULL AND ts IS NOT NULL GROUP BY ALL
), gaps AS (
  SELECT definition,epoch(ts-lag(ts) OVER(PARTITION BY definition,client_id ORDER BY ts))/86400
    AS days FROM variants WHERE client_id IS NOT NULL AND ts IS NOT NULL
)
SELECT definition,count(*) AS purchasers,count_if(purchases>=2) AS repeat_purchasers,
  min(purchases) AS minimum,median(purchases) AS median,max(purchases) AS maximum,
  quantile_cont(purchases,0.9) AS p90,median(span_days) AS median_span_days,
  (SELECT median(days) FROM gaps g WHERE g.definition=c.definition) AS median_gap_days,
  (SELECT quantile_cont(days,0.9) FROM gaps g WHERE g.definition=c.definition) AS p90_gap_days,
  (SELECT count_if(days=0) FROM gaps g WHERE g.definition=c.definition) AS zero_gaps,
  (SELECT count_if(days>0 AND days<=1.0/24) FROM gaps g WHERE g.definition=c.definition)
    AS positive_gaps_within_hour
FROM counts c GROUP BY definition ORDER BY definition;
