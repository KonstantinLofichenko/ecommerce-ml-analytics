-- GoogleSQL. UNEXECUTED: no authorized local BigQuery access.
SELECT p.key, COUNT(*) AS occurrences,
  COUNTIF(p.value.int_value IS NOT NULL) AS integer_values,
  COUNTIF(p.value.string_value IS NOT NULL) AS string_values,
  COUNTIF(p.value.double_value IS NOT NULL) AS double_values
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`, UNNEST(event_params) p
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
GROUP BY p.key ORDER BY occurrences DESC, p.key;
