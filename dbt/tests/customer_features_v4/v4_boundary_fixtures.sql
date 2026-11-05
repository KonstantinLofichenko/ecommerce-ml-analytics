{{ config(tags=['customer_features_v4']) }}
WITH toDateTime('2023-02-01 12:00:00','UTC') AS anchor,
 events AS (
 SELECT arrayJoin([anchor-INTERVAL 30 DAY-INTERVAL 1 SECOND,
 anchor-INTERVAL 30 DAY,anchor-INTERVAL 1 SECOND,
 anchor-INTERVAL 1 SECOND,anchor,anchor+INTERVAL 1 SECOND]) AS ts
 )
SELECT 1 FROM events HAVING countIf(ts>=anchor-INTERVAL 30 DAY AND ts<anchor)!=3
 OR dateDiff('day',toDate(anchor),addDays(toDate(anchor),30))!=30
 OR (SELECT countIf(gap BETWEEN 1 AND 30)
     FROM (SELECT arrayJoin([0,1,30,31]) AS gap))!=2
