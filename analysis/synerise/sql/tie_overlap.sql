SELECT 'page_cart' AS stage,count(*) AS equal_time_client_pairs FROM (
 SELECT DISTINCT p.client_id,p.ts FROM page_visit p
 JOIN (SELECT DISTINCT client_id,ts FROM add_to_cart) c USING(client_id,ts))
UNION ALL SELECT 'search_cart',count(*) FROM (
 SELECT DISTINCT p.client_id,p.ts FROM search_query p
 JOIN (SELECT DISTINCT client_id,ts FROM add_to_cart) c USING(client_id,ts))
UNION ALL SELECT 'cart_buy',count(*) FROM (
 SELECT DISTINCT p.client_id,p.ts FROM add_to_cart p
 JOIN (SELECT DISTINCT client_id,ts FROM product_buy) c USING(client_id,ts));
