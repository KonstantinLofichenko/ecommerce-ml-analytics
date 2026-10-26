WITH occasions AS (
  SELECT client_id,ts,count(*) AS events,count(DISTINCT sku) AS skus FROM product_buy
  GROUP BY client_id,ts
)
SELECT count(*) AS occasions,count_if(events>1) AS multi_event_occasions,
  count_if(skus>1) AS multi_sku_occasions,max(events) AS maximum_events,
  sum(events) AS purchase_events FROM occasions;
