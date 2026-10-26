-- Pinned to this validated historical source release; intentional refresh requires reconciliation.
SELECT 'product metric baseline changed' AS issue FROM {{ ref('fct_synerise_funnel_by_product') }} HAVING count() != 1444160 OR toString(sum(toUInt256(cityHash64(tuple(sku, cart_customers, purchase_customers, conversion_rate))))) != '13315736359173369104616047'
UNION ALL
SELECT 'category metric baseline changed' AS issue FROM {{ ref('fct_synerise_funnel_by_category') }} HAVING count() != 6880 OR toString(sum(toUInt256(cityHash64(tuple(category_id, cart_customers, purchase_customers, conversion_rate))))) != '63679153348467984232959'
UNION ALL
SELECT 'dim_synerise_categories row count' AS issue FROM {{ ref('dim_synerise_categories') }} HAVING count()!=6912
UNION ALL
SELECT 'dim_synerise_products row count' AS issue FROM {{ ref('dim_synerise_products') }} HAVING count()!=1534050
