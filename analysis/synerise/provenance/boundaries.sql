-- Proximity diagnostics only. Events are neither shifted nor rewritten.
WITH cutoffs AS (SELECT unnest([TIMESTAMP '2022-08-01',TIMESTAMP '2022-09-01',
  TIMESTAMP '2022-10-01',TIMESTAMP '2022-11-01']) AS snapshot),
buys AS (SELECT client_id,CAST(timestamp AS TIMESTAMP) AS ts
 FROM read_parquet('data/external/synerise/source/product_buy.parquet'))
SELECT snapshot,
 count_if(ts>=snapshot-INTERVAL 1 HOUR AND ts<snapshot+INTERVAL 1 HOUR) AS events_near_cutoff,
 count(DISTINCT client_id) FILTER (WHERE ts>=snapshot-INTERVAL 1 HOUR
   AND ts<snapshot+INTERVAL 1 HOUR) AS clients_near_cutoff,
 count_if(ts=snapshot) AS events_exactly_at_cutoff,
 count_if(ts>=snapshot+INTERVAL 14 DAY-INTERVAL 1 HOUR
   AND ts<snapshot+INTERVAL 14 DAY+INTERVAL 1 HOUR) AS events_near_label_end,
 count(DISTINCT client_id) FILTER (WHERE ts>=snapshot+INTERVAL 14 DAY-INTERVAL 1 HOUR
   AND ts<snapshot+INTERVAL 14 DAY+INTERVAL 1 HOUR) AS clients_near_label_end
FROM buys CROSS JOIN cutoffs GROUP BY snapshot ORDER BY snapshot;
