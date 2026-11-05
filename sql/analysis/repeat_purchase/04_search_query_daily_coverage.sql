-- Final validated: Daily counts, valid timestamp bounds, parse/format/offset checks for search_query.
-- Recovered from: /tmp/v4_coverage.py (executed coverage investigation).
-- Raw-source scan. UTC parsing is a computational convention, not verified source timezone.
SELECT substring(timestamp,1,10) AS day,count() AS events,
 min(parseDateTimeBestEffortOrNull(timestamp,'UTC')) AS first_ts,
 max(parseDateTimeBestEffortOrNull(timestamp,'UTC')) AS last_ts,
 countIf(isNull(parseDateTimeBestEffortOrNull(timestamp,'UTC'))) AS invalid,
 countIf(NOT match(timestamp,'^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$')) AS nonstandard,
 countIf(match(timestamp,'(Z|[+-][0-9]{2}:?[0-9]{2})$')) AS explicit_offset
  FROM synerise_raw.search_query
GROUP BY day
ORDER BY day;
