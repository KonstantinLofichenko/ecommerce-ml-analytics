SELECT
    round(p75_minutes / 60.0, 2) AS "P75 (hours)"
FROM synerise_analytics.fct_synerise_time_to_conversion
WHERE metric_scope = 'customer';