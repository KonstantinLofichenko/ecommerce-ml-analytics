SELECT
    round(p90_minutes / 1440.0, 2) AS "P90 (days)"
FROM synerise_analytics.fct_synerise_time_to_conversion
WHERE metric_scope = 'customer';