-- GoogleSQL. UNEXECUTED: no authorized local BigQuery access.
-- Most expensive candidate: all columns, including repeated-array order.
-- Excludes source table provenance to detect identical payloads across daily tables.
WITH payloads AS (
  SELECT TO_JSON_STRING(e) AS payload
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` e
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
), groups AS (
  SELECT payload, COUNT(*) AS multiplicity FROM payloads GROUP BY payload
)
SELECT multiplicity, COUNT(*) AS groups, SUM(multiplicity) AS rows,
  SUM(multiplicity - 1) AS excess_rows
FROM groups GROUP BY multiplicity ORDER BY multiplicity;
