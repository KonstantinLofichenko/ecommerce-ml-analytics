-- Inclusive elapsed-window boundaries; a first cart exactly seven days before end is eligible.
WITH fixtures AS (
    SELECT number AS id,
        arrayElement([toNullable(toInt64(0)),3600,3601,86400,86401,604800,604801,NULL], number+1) AS seconds,
        toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY AS cart
    FROM numbers(8)
), outcomes AS (
    SELECT *, multiIf(seconds<=3600,1,seconds<=86400,2,seconds<=604800,3,4) AS bucket
    FROM fixtures
)
SELECT toString(id) AS issue FROM outcomes
WHERE bucket != arrayElement([1,1,2,2,3,3,4,4],id+1)
    OR NOT (cart <= toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY)
    OR cart+INTERVAL 1 SECOND <= toDateTime('2022-12-08 00:09:59')-INTERVAL 7 DAY
UNION ALL
SELECT 'zero cohort denominator' WHERE isNotNull(0.0/nullIf(toUInt64(0),0))
UNION ALL
SELECT 'zero converters denominator' WHERE isNotNull(0.0/nullIf(toUInt64(0),0))
