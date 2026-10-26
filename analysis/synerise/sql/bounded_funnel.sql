-- $days is rendered as an integer by the runner; -1 denotes no window bound.
-- ASOF matches latest strictly preceding stage; stage anchors are nondecreasing.
WITH page_search AS (
  SELECT s.client_id,s.ts,p.ts AS anchor FROM search_query s
  ASOF INNER JOIN page_visit p ON s.client_id=p.client_id AND s.ts>p.ts
  WHERE ($days<0 OR s.ts-p.ts<=INTERVAL '$days DAY')
), page_cart AS (
  SELECT c.client_id,c.ts,p.ts AS anchor FROM add_to_cart c
  ASOF INNER JOIN page_visit p ON c.client_id=p.client_id AND c.ts>p.ts
  WHERE ($days<0 OR c.ts-p.ts<=INTERVAL '$days DAY')
), search_cart AS (
  SELECT c.client_id,c.ts,s.anchor FROM add_to_cart c
  ASOF INNER JOIN page_search s ON c.client_id=s.client_id AND c.ts>s.ts
  WHERE ($days<0 OR c.ts-s.anchor<=INTERVAL '$days DAY')
), page_buy AS (
  SELECT b.client_id,b.ts,c.anchor FROM product_buy b
  ASOF INNER JOIN page_cart c ON b.client_id=c.client_id AND b.ts>c.ts
  WHERE ($days<0 OR b.ts-c.anchor<=INTERVAL '$days DAY')
), search_buy AS (
  SELECT b.client_id,b.ts,c.anchor FROM product_buy b
  ASOF INNER JOIN search_cart c ON b.client_id=c.client_id AND b.ts>c.ts
  WHERE ($days<0 OR b.ts-c.anchor<=INTERVAL '$days DAY')
), sku_buy AS (
  SELECT b.client_id,b.sku,b.ts,c.ts AS cart_ts FROM product_buy b
  ASOF INNER JOIN add_to_cart c ON b.client_id=c.client_id AND b.sku=c.sku AND b.ts>c.ts
  WHERE ($days<0 OR b.ts-c.ts<=INTERVAL '$days DAY')
)
SELECT $days AS window_days,
  (SELECT count(DISTINCT client_id) FROM page_visit) AS page_customers,
  (SELECT count(DISTINCT client_id) FROM page_search) AS page_search,
  (SELECT count(DISTINCT client_id) FROM page_cart) AS page_cart,
  (SELECT count(DISTINCT client_id) FROM search_cart) AS page_search_cart,
  (SELECT count(DISTINCT client_id) FROM page_buy) AS page_cart_buy,
  (SELECT count(DISTINCT client_id) FROM search_buy) AS page_search_cart_buy,
  (SELECT count(DISTINCT client_id) FROM sku_buy) AS sku_cart_buy_customers,
  (SELECT count(*) FROM (SELECT DISTINCT client_id,sku FROM sku_buy)) AS sku_cart_buy_pairs;
