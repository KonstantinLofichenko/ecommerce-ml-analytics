-- Execute the same raw-rebuild macros against small adversarial histories.
WITH properties AS (
    SELECT toInt64(10) sku, toInt64(1) category_id
    UNION ALL SELECT 11, 1 UNION ALL SELECT 20, 2
), carts AS (
    SELECT 1 client_id, 10 sku, '2022-08-01 10:00:00' event_time_source
    UNION ALL SELECT 1, 10, '2022-08-01 10:00:00' -- duplicate customer action
    UNION ALL SELECT 2, 10, '2022-08-02 10:00:00'
    UNION ALL SELECT 3, 11, '2022-08-01 10:00:00'
    UNION ALL SELECT 4, 20, '2022-08-01 10:00:00'
), buys AS (
    SELECT 1 client_id, 10 sku, '2022-08-01 10:00:00' event_time_source -- ties accepted
    UNION ALL SELECT 2, 10, '2022-08-01 10:00:00' -- purchase before cart rejected
    UNION ALL SELECT 3, 10, '2022-10-01 10:00:00' -- other SKU, same category; no deadline
    UNION ALL SELECT 4, 10, '2022-08-01 11:00:00' -- wrong category rejected
    UNION ALL SELECT 5, 20, '2022-08-01 11:00:00' -- purchaser without cart excluded
), product_actual AS ({{ synerise_product_funnel_metrics('carts', 'buys', 'properties') }}),
category_actual AS ({{ synerise_category_funnel_metrics('carts', 'buys', 'properties') }})
SELECT 'product' issue FROM product_actual
WHERE (sku=10 AND (cart_customers!=2 OR purchase_customers!=1))
    OR (sku IN (11,20) AND (cart_customers!=1 OR purchase_customers!=0))
    OR sku NOT IN (10,11,20)
UNION ALL SELECT 'category' FROM category_actual
WHERE (category_id=1 AND (cart_customers!=3 OR purchase_customers!=2))
    OR (category_id=2 AND (cart_customers!=1 OR purchase_customers!=0))
    OR category_id NOT IN (1,2)
UNION ALL SELECT 'product row count' FROM product_actual HAVING count()!=3
UNION ALL SELECT 'category row count' FROM category_actual HAVING count()!=2
