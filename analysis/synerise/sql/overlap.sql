WITH cutoffs AS (SELECT unnest([TIMESTAMP '2022-08-01',TIMESTAMP '2022-09-01',
  TIMESTAMP '2022-10-01',TIMESTAMP '2022-11-01']) AS snapshot),
firsts AS (SELECT client_id,min(ts) AS first_purchase FROM product_buy GROUP BY client_id)
SELECT a.snapshot AS earlier,b.snapshot AS later,count(*) AS shared_eligible_clients
FROM cutoffs a JOIN cutoffs b ON a.snapshot<b.snapshot
JOIN firsts f ON f.first_purchase<a.snapshot AND f.first_purchase<b.snapshot
GROUP BY a.snapshot,b.snapshot ORDER BY a.snapshot,b.snapshot;
