{{ config(tags=['synerise_retention']) }}
-- Small adversarial fixture: repeated rows, absent month, re-entry, year rollover,
-- partial cohort and partial outcome months. This writes no fixture tables.
WITH events AS (
 SELECT tupleElement(x,1) AS client_id, toDate(tupleElement(x,2)) AS purchase_date
 FROM (SELECT arrayJoin([
   tuple(1,'2022-12-03'),tuple(1,'2022-12-03'),tuple(1,'2023-02-02'),
   tuple(2,'2022-11-25'),tuple(3,'2023-03-02')
 ]) AS x)
), firsts AS (
 SELECT client_id,toStartOfMonth(min(purchase_date)) AS cohort_month
 FROM events GROUP BY client_id
), months AS (
 SELECT DISTINCT e.client_id,f.cohort_month,toStartOfMonth(e.purchase_date) AS purchase_month
 FROM events e INNER JOIN firsts f USING(client_id)
), grid AS (
 SELECT cohort_month,arrayJoin(range(4)) AS month_number,
 addMonths(cohort_month,toInt32(month_number)) AS purchase_month
 FROM firsts
 WHERE cohort_month > toDate('2022-11-01')
 AND purchase_month < toDate('2023-03-01')
), actual AS (
 SELECT g.month_number, countIf(m.client_id IS NOT NULL) AS retained
 FROM grid g LEFT JOIN months m USING(cohort_month,purchase_month)
 GROUP BY g.month_number
), expected AS (
 SELECT tupleElement(x,1) AS month_number,tupleElement(x,2) AS retained
 FROM (SELECT arrayJoin([tuple(0,1),tuple(1,0),tuple(2,1)]) AS x)
)
SELECT coalesce(a.month_number,e.month_number) AS month_number
FROM actual a FULL OUTER JOIN expected e USING(month_number)
WHERE a.month_number IS NULL OR e.month_number IS NULL OR a.retained!=e.retained
SETTINGS join_use_nulls=1
