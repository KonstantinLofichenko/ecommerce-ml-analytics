SELECT
    round(p50_minutes, 2) AS "Median (minutes)"
FROM synerise_analytics.fct_synerise_time_to_conversion
WHERE metric_scope = 'customer';