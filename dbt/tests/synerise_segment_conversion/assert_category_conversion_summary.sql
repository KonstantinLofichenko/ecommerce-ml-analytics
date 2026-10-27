WITH expected AS (
    SELECT category_id, count() AS carts, sum(converted) AS converters,
        countIf(first_cart_time<=toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY) AS eligible,
        countIf(first_cart_time<=toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY AND first_purchase_time<=first_cart_time+INTERVAL 1 HOUR) AS h1,
        countIf(first_cart_time<=toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY AND first_purchase_time<=first_cart_time+INTERVAL 24 HOUR) AS h24,
        countIf(first_cart_time<=toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY AND first_purchase_time<=first_cart_time+INTERVAL 7 DAY) AS d7
    FROM {{ ref('int_synerise_category_conversion_times') }} GROUP BY category_id
)
SELECT f.category_id
FROM {{ ref('fct_synerise_time_to_conversion_by_category') }} f
FULL OUTER JOIN expected e ON f.category_id=e.category_id
WHERE f.category_id IS NULL OR e.category_id IS NULL OR f.cart_customers!=e.carts
    OR f.converted_customers!=e.converters OR f.eligible_customers_7d!=e.eligible
    OR f.converted_1h!=e.h1 OR f.converted_24h!=e.h24 OR f.converted_7d!=e.d7
    OR NOT (f.converted_1h<=f.converted_24h AND f.converted_24h<=f.converted_7d AND f.converted_7d<=f.eligible_customers_7d)
    OR f.converted_customers>f.cart_customers
    OR (f.converted_customers=0 AND (f.p50_seconds IS NOT NULL OR f.p75_seconds IS NOT NULL OR f.p90_seconds IS NOT NULL OR f.avg_seconds IS NOT NULL))
    OR (f.converted_customers>0 AND (f.p50_seconds IS NULL OR f.p75_seconds IS NULL OR f.p90_seconds IS NULL OR f.avg_seconds IS NULL))
    OR f.p50_seconds<0 OR f.p50_seconds>f.p75_seconds OR f.p75_seconds>f.p90_seconds
    OR ifNull(f.conversion_1h_rate,-1)!=ifNull(toFloat64(e.h1)/nullIf(e.eligible,0),-1)
    OR ifNull(f.conversion_24h_rate,-1)!=ifNull(toFloat64(e.h24)/nullIf(e.eligible,0),-1)
    OR ifNull(f.conversion_7d_rate,-1)!=ifNull(toFloat64(e.d7)/nullIf(e.eligible,0),-1)
SETTINGS join_use_nulls=1, join_algorithm='grace_hash', max_bytes_in_join=67108864,
    max_threads=1, max_memory_usage=1073741824, max_block_size=8192,
    optimize_aggregation_in_order=1, max_bytes_before_external_group_by=67108864
