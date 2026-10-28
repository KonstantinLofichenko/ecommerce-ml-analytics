-- Reconstructed from saved GUI/MBQL question 42; not recovered generated SQL.
-- Optional variables are Metabase Field Filters mapped to this table, without alias.
-- Preserve the saved top-ten ordering; equal cart counts have no secondary sort.
SELECT *
FROM synerise_analytics.fct_synerise_funnel_by_category
WHERE 1 = 1
[[AND {{category_level_1}}]]
[[AND {{category_level_2}}]]
[[AND {{category_level_3}}]]
[[AND {{category_level_4}}]]
ORDER BY cart_customers DESC
LIMIT 10
