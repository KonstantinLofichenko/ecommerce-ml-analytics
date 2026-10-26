-- Coverage only, not a production feature table. No future events join historical rows.
WITH snapshot AS (SELECT MAX(snapshot) AS t FROM snapshots), eligible AS (
 SELECT client_id FROM product_buy,snapshot WHERE ts<t GROUP BY client_id
), history AS (
 SELECT e.client_id,count_if(kind='page_visit') AS pages,
   count_if(kind='search_query') AS searches,count_if(kind='add_to_cart') AS carts,
   count_if(kind='remove_from_cart') AS removes,count_if(kind='product_buy') AS buys,
   count(DISTINCT sku) FILTER (WHERE kind='add_to_cart') AS cart_skus,
   count(DISTINCT CAST(ts AS DATE)) AS active_days,max(ts) AS last_event
 FROM events e JOIN eligible g USING(client_id) CROSS JOIN snapshot
 WHERE ts<t AND ts>=t-INTERVAL 30 DAY GROUP BY e.client_id
)
SELECT (SELECT t FROM snapshot) AS snapshot,count(*) AS eligible,
 count_if(h.client_id IS NULL) AS zero_activity_30d,
 count_if(coalesce(pages,0)=0) AS zero_page_visits_30d,
 count_if(coalesce(searches,0)=0) AS zero_searches_30d,
 count_if(coalesce(carts,0)=0) AS zero_cart_adds_30d,
 count_if(coalesce(removes,0)=0) AS zero_cart_removals_30d,
 count_if(coalesce(buys,0)=0) AS zero_purchases_30d,
 median(coalesce(active_days,0)) AS median_active_days,
 median(coalesce(cart_skus,0)) AS median_cart_skus,
 max(last_event) AS maximum_historical_timestamp
FROM eligible g LEFT JOIN history h USING(client_id);
