{{ config(tags=['synerise_retention']) }}
-- Independent small fixtures: year rollover, skipped month, inclusive month zero.
SELECT 1 WHERE dateDiff('month',toDate('2022-12-01'),toDate('2023-02-01')) != 2
 OR addMonths(toDate('2022-12-01'),1) != toDate('2023-01-01')
 OR (SELECT uniqExact(toDate(x)) FROM (SELECT arrayJoin(['2023-01-01','2023-01-01','2023-01-03']) x)) != 2
