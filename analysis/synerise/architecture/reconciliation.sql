-- DESIGN examples only; never executed by this phase.
-- raw_db is an explicit immutable Synerise release database, never ecommerce.
-- bucket: UInt16 in 0..63. Run sequentially; compare with fresh Parquet validation.
SELECT count() AS rows,min(timestamp) AS first_source_text,max(timestamp) AS last_source_text,
  countIf(isNull(client_id)) AS null_clients,countIf(isNull(timestamp)) AS null_times,
  countIf(isNull(url)) AS null_urls,uniqExact(client_id) AS clients
FROM {raw_db:Identifier}.page_visit
WHERE positiveModulo(client_id,64)={bucket:UInt16};

-- Canonical framing example for non-nullable original page fields in schema order.
-- Python counterpart uses len(value.encode('utf-8')), decimal signed Int64, MD5 bytes.
-- Digests are multiset evidence, not an event ID or formal adversarial proof.
WITH hashed AS (
  SELECT hex(MD5(concat('page_visit|',
    toString(length(toString(client_id))),':',toString(client_id),
    toString(length(timestamp)),':',timestamp,
    toString(length(toString(url))),':',toString(url)))) AS h
  FROM {raw_db:Identifier}.page_visit
  WHERE positiveModulo(client_id,64)={bucket:UInt16}
), halves AS (
 SELECT reinterpretAsUInt64(reverse(unhex(substring(h,1,16)))) AS a,
        reinterpretAsUInt64(reverse(unhex(substring(h,17,16)))) AS b FROM hashed
)
SELECT count() AS rows,sum(toUInt128(a)) AS sum_half_1,
 sum(toUInt128(b)) AS sum_half_2,groupBitXor(a) AS xor_half_1 FROM halves;

-- Exact original-row duplicate multiplicities, one month and client bucket at a time.
SELECT multiplicity,count() AS groups,sum(multiplicity-1) AS excess_rows
FROM (
 SELECT client_id,timestamp,url,count() AS multiplicity
 FROM {raw_db:Identifier}.page_visit
 WHERE source_day>={month_start:Date32} AND source_day<{next_month:Date32}
   AND positiveModulo(client_id,64)={bucket:UInt16}
 GROUP BY client_id,timestamp,url
) GROUP BY multiplicity ORDER BY multiplicity;

-- No unique constraint/deduplication engine; uniqueness is an acceptance assertion.
SELECT count() AS properties,uniqExact(sku) AS distinct_skus
FROM {raw_db:Identifier}.product_properties;

SELECT count() AS unmatched_purchase_rows
FROM {raw_db:Identifier}.product_buy b
LEFT ANTI JOIN {raw_db:Identifier}.product_properties p ON b.sku=p.sku
WHERE positiveModulo(b.client_id,64)={bucket:UInt16};

-- Source-clock materialization check: no timezone conversion.
SELECT countIf(toString(tupleElement(event_time_source,'day'))!=substring(timestamp,1,10))
 AS wrong_day,
 countIf(tupleElement(event_time_source,'second_of_day')!=
   toUInt32(substring(timestamp,12,2))*3600+toUInt32(substring(timestamp,15,2))*60+
   toUInt32(substring(timestamp,18,2))) AS wrong_time
FROM {raw_db:Identifier}.page_visit;
