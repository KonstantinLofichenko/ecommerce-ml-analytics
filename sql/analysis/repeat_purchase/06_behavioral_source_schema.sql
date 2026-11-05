-- Final validated: Inspect customer/timestamp/page identifier types.
-- Recovered from: ClickHouse query_log, 2026-10-29 16:28:03.
SELECT table,name,type
  FROM system.columns
 WHERE database='synerise_raw'
   AND table IN ('page_visit','add_to_cart','remove_from_cart','search_query')
   AND name IN ('client_id','timestamp','url')
ORDER BY table,name;
