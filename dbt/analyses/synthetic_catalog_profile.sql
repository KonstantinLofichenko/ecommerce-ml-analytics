-- Read-only report of all staging candidates, including explicit exclusions.
WITH candidates AS ({{ amazon_synthetic_candidates() }})
SELECT source_department, classification_status, count() AS products
FROM candidates
GROUP BY source_department, classification_status
ORDER BY source_department, classification_status
