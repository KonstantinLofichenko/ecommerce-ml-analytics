SELECT
    multiIf(
        distinct_purchase_dates >= 6, '6+',
        toString(distinct_purchase_dates)
    ) AS purchase_dates_group,
    count() AS customers
FROM synerise_analytics.fct_synerise_customer_repeat_purchase
GROUP BY purchase_dates_group
ORDER BY
    if(purchase_dates_group = '6+', 6,
       toUInt64(purchase_dates_group));
