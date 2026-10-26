"""DDL renderer shared by design files and the bounded, isolated benchmark only."""

import re
from datetime import datetime

COLUMNS = {
    "page_visit": [("client_id", "Int64"), ("timestamp", "String"), ("url", "Int64")],
    "search_query": [("client_id", "Int64"), ("timestamp", "String"), ("query", "String")],
    "add_to_cart": [("client_id", "Int64"), ("timestamp", "String"), ("sku", "Int64")],
    "remove_from_cart": [("client_id", "Int64"), ("timestamp", "String"), ("sku", "Int64")],
    "product_buy": [("client_id", "Int64"), ("timestamp", "String"), ("sku", "Int64")],
    "product_properties": [
        ("sku", "Int64"),
        ("category", "Int64"),
        ("price", "Int64"),
        ("name", "String"),
    ],
}


def ddl(database, table, source, digest, archive, release, attempt):
    for value in (database, table):
        if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("Unsafe SQL identifier")
    columns = [f"`{name}` {kind} CODEC(ZSTD(1))" for name, kind in COLUMNS[source]]
    columns += [
        f"_source_file LowCardinality(String) DEFAULT '{source}.parquet'",
        f"_source_sha256 FixedString(64) DEFAULT '{digest}'",
        f"_archive_sha256 FixedString(64) DEFAULT '{archive}'",
        f"_release_id UUID DEFAULT toUUID('{release}')",
        f"_attempt_id UUID DEFAULT toUUID('{attempt}')",
    ]
    if source != "product_properties":
        columns += [
            "event_time_source Tuple(day Date32, second_of_day UInt32) MATERIALIZED "
            "tuple(toDate32(substring(timestamp,1,10)), "
            "toUInt32(toUInt32(substring(timestamp,12,2))*3600 + "
            "toUInt32(substring(timestamp,15,2))*60 + toUInt32(substring(timestamp,18,2))))",
            "source_day Date32 ALIAS tupleElement(event_time_source,'day')",
            "source_second Int64 ALIAS dateDiff('day',toDate32('1970-01-01'),source_day)*86400 "
            "+ toInt64(tupleElement(event_time_source,'second_of_day'))",
            "CONSTRAINT clock_shape CHECK match(timestamp,"
            "'^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$')",
            "CONSTRAINT clock_hms CHECK toUInt32(substring(timestamp,12,2))<24 "
            "AND toUInt32(substring(timestamp,15,2))<60 "
            "AND toUInt32(substring(timestamp,18,2))<60",
            "CONSTRAINT clock_date CHECK toString(tupleElement(event_time_source,'day'))"
            "=substring(timestamp,1,10)",
        ]
        partition = "PARTITION BY toYYYYMM(tupleElement(event_time_source,1))"
        key = "client_id,event_time_source" + (
            ",sku"
            if any(n == "sku" for n, _ in COLUMNS[source])
            else ",url"
            if source == "page_visit"
            else ""
        )
    else:
        partition = ""
        key = "sku"
    return (
        f"CREATE TABLE `{database}`.`{table}` (\n  "
        + ",\n  ".join(columns)
        + f"\n) ENGINE=MergeTree\n{partition}\nORDER BY ({key})\n"
        "SETTINGS index_granularity=8192\nCOMMENT 'synerise architecture isolated v1'"
    )


def civil_second(text):
    """Reference civil ordinal, intentionally not a timezone-aware Unix epoch."""
    parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    return int((parsed - datetime(1970, 1, 1)).total_seconds())
