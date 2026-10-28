SELECT
    1 AS window_order,
    '1 hour' AS time_window,
    conversion_1h_pct AS conversion_rate
FROM synerise_analytics.fct_synerise_time_to_conversion

UNION ALL

SELECT
    2 AS window_order,
    '24 hours' AS time_window,
    conversion_24h_pct AS conversion_rate
FROM synerise_analytics.fct_synerise_time_to_conversion

UNION ALL

SELECT
    3 AS window_order,
    '7 days' AS time_window,
    conversion_7d_pct AS conversion_rate
FROM synerise_analytics.fct_synerise_time_to_conversion

ORDER BY window_order;