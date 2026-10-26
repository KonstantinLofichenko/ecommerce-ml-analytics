"""Canonical source/destination reconciliation, including duplicate multiplicity."""

from decimal import Decimal

import duckdb

from ecommerce_analytics.ingestion.clickhouse import ClickHouse, MigrationError, identifier

ORIGINAL = (
    "event_time",
    "event_type",
    "product_id",
    "category_id",
    "category_code",
    "brand",
    "price",
    "user_id",
    "user_session",
)
SOURCE_COLUMNS = (*ORIGINAL, "month", "event_time_utc")
DESTINATION = (*ORIGINAL, "month", "event_time_utc", "price_raw")
TYPES = {
    "event_time": "Nullable(String)",
    "event_type": "LowCardinality(Nullable(String))",
    "product_id": "Nullable(String)",
    "category_id": "Nullable(String)",
    "category_code": "LowCardinality(Nullable(String))",
    "brand": "LowCardinality(Nullable(String))",
    "price": "Nullable(Decimal(18, 2))",
    "user_id": "Nullable(String)",
    "user_session": "Nullable(String)",
    "month": "String",
    "event_time_utc": "Nullable(DateTime64(6, 'UTC'))",
    "price_raw": "Nullable(String)",
}
MARKER = "ecommerce-ml historical raw migration v1"


def source_schema(con: duckdb.DuckDBPyConnection) -> None:
    columns = {r[0]: r[1] for r in con.execute("DESCRIBE raw_events").fetchall()}
    if columns != {
        c: ("TIMESTAMP" if c == "event_time_utc" else "VARCHAR") for c in SOURCE_COLUMNS
    }:
        raise MigrationError("raw_events must match the validated 11-column DuckDB schema.")
    bad = con.execute("""
        SELECT count(*) FROM raw_events WHERE
          month IS NULL OR NOT regexp_full_match(month, '[0-9]{4}-(0[1-9]|1[0-2])')
          OR (price IS NOT NULL AND (NOT regexp_full_match(price,
            '[+-]?[0-9]{1,16}(\\.[0-9]{1,2})?') OR try_cast(price AS DECIMAL(18,2)) IS NULL))
          OR (event_time IS NOT NULL AND try_cast(event_time AS TIMESTAMPTZ) IS NULL)
          OR (cast(try_cast(event_time AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS TIMESTAMP)
              IS DISTINCT FROM event_time_utc)
    """).fetchone()[0]
    if bad:
        raise MigrationError(f"{bad} invalid prices/months/timestamps; no rows will be coerced.")


def canonical_sql(engine: str) -> str:
    """Length-prefixed UTF-8 original values + provenance + normalized time/money.

    -1: encodes NULL; 0: encodes an empty string. Separators cannot collide with
    arbitrary Unicode, tabs, delimiters or embedded newlines in source values.
    """
    values = [
        ("price_raw" if c == "price" else c) if engine == "ch" else c for c in (*ORIGINAL, "month")
    ]
    if engine == "ch":
        values += [
            "formatDateTime(event_time_utc, '%Y-%m-%d %H:%i:%S.%f', 'UTC')",
            "toString(toInt64(price * 100))",
        ]
        parts = [
            f"if(isNull({v}), '-1:', concat(toString(length({v})), ':', ifNull({v}, '')))"
            for v in values
        ]
        return "concat(" + ", ".join(parts) + ")"
    values += [
        "strftime(event_time_utc, '%Y-%m-%d %H:%M:%S.%f')",
        "cast(cast(price AS DECIMAL(18,2)) * 100 AS BIGINT)::VARCHAR",
    ]
    return (
        "concat("
        + ", ".join(
            f"CASE WHEN {v} IS NULL THEN '-1:' ELSE octet_length(encode({v}))::VARCHAR "
            f"|| ':' || {v} END"
            for v in values
        )
        + ")"
    )


def _normalize(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        converted = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                value = str(value)
            elif value is not None and key in ("minimum_time", "maximum_time"):
                value = str(value)
            elif value is not None and key != "event_type":
                value = int(value)
            converted[key] = value
        result.append(converted)
    return result


def profile(
    con: duckdb.DuckDBPyConnection,
    client: ClickHouse | None = None,
    qualified_table: str = "",
    progress=None,
) -> dict:
    engine = "ch" if client else "duck"
    if client:
        query = client.query
        table = qualified_table
        months = [r["month"] for r in query(f"SELECT DISTINCT month FROM {table} ORDER BY month")]
    else:

        def query(sql: str) -> list[dict]:
            cursor = con.execute(sql)
            names = [c[0] for c in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

        table = "raw_events"
        months = [r["month"] for r in query("SELECT DISTINCT month FROM raw_events ORDER BY month")]
    report = {}
    for month in months:
        # Source-schema validation enforces the restricted YYYY-MM literal format.
        if not isinstance(month, str) or len(month) != 7 or not month.replace("-", "").isdigit():
            raise MigrationError("Invalid destination month.")
        if progress:
            progress("reconcile_partition", engine=engine, month=month)
        where = f"month = '{month}'"
        if client:
            digest = f"hex(MD5({canonical_sql(engine)}))"
            h1 = "reinterpretAsUInt64(reverse(unhex(substring(h,1,16))))"
            h2 = "reinterpretAsUInt64(reverse(unhex(substring(h,17,16))))"
            minimum = "formatDateTime(min(event_time_utc),'%Y-%m-%d %H:%i:%S.%f','UTC')"
            maximum = minimum.replace("min(", "max(")
            money = "sum(toInt128(price * 100))"
            nulls = ", ".join(f"countIf(isNull({c})) AS null_{c}" for c in DESTINATION)
            unique = "uniqExact(user_id)"
            total = (
                f"sum(toUInt128({h1})) AS checksum_sum_1, sum(toUInt128({h2})) AS checksum_sum_2"
            )
            xor = f"groupBitXor({h1}) AS checksum_xor"
        else:
            digest = f"md5({canonical_sql(engine)})"
            h1 = "cast('0x' || substr(h,1,16) AS UBIGINT)"
            h2 = "cast('0x' || substr(h,17,16) AS UBIGINT)"
            minimum = "strftime(min(event_time_utc),'%Y-%m-%d %H:%M:%S.%f')"
            maximum = minimum.replace("min(", "max(")
            money = "coalesce(sum(cast(cast(price AS DECIMAL(18,2))*100 AS HUGEINT)),0)"
            nulls = ", ".join(
                f"count(*) FILTER (WHERE {'price' if c == 'price_raw' else c} IS NULL) AS null_{c}"
                for c in DESTINATION
            )
            unique = "count(DISTINCT user_id)"
            total = (
                f"sum(cast({h1} AS HUGEINT)) AS checksum_sum_1, "
                f"sum(cast({h2} AS HUGEINT)) AS checksum_sum_2"
            )
            xor = f"bit_xor({h1}) AS checksum_xor"
        aggregates = query(f"""
            WITH rows AS (SELECT *, {digest} AS h FROM {table} WHERE {where})
            SELECT count(*) AS rows, {unique} AS distinct_users,
              {minimum} AS minimum_time, {maximum} AS maximum_time,
              {money} AS price_minor_units, {nulls}, {total}, {xor} FROM rows
        """)
        types = query(
            f"SELECT event_type,count(*) AS rows FROM {table} WHERE {where} "
            "GROUP BY event_type ORDER BY event_type NULLS LAST"
        )
        original = ",".join("price_raw" if c == "price" and client else c for c in ORIGINAL)
        duplicates = query(f"""
            SELECT multiplicity, count(*) AS groups FROM
              (SELECT {original}, count(*) AS multiplicity FROM {table}
               WHERE {where} GROUP BY {original})
            GROUP BY multiplicity ORDER BY multiplicity
        """)
        report[month] = {
            "aggregates": _normalize(aggregates),
            "event_types": _normalize(types),
            "duplicates": _normalize(duplicates),
        }
    # Global distinct users are not additive across monthly partitions.
    report["_global"] = _normalize(
        query(
            f"SELECT count(*) AS rows, "
            f"{'uniqExact(user_id)' if client else 'count(DISTINCT user_id)'} AS distinct_users "
            f"FROM {table}"
        )
    )
    return report


def compare(reference: dict, destination: dict) -> list[dict]:
    differences = []
    for key in sorted(set(reference) | set(destination)):
        if reference.get(key) != destination.get(key):
            differences.append(
                {
                    "partition": key,
                    "reference": reference.get(key),
                    "destination": destination.get(key),
                }
            )
    return differences


def check_destination(client: ClickHouse, database: str, table: str) -> None:
    qualified = f"{identifier(database)}.{identifier(table)}"
    actual = {r["name"]: r["type"] for r in client.query(f"DESCRIBE TABLE {qualified}")}
    if actual != TYPES:
        raise MigrationError("Destination schema differs from the migration contract.")
    info = client.query(
        f"SELECT engine, comment FROM system.tables WHERE database='{database}' AND name='{table}'"
    )[0]
    if info["engine"] != "MergeTree" or info["comment"] != MARKER:
        raise MigrationError("Refusing to replace an unmanaged/non-MergeTree destination.")


def ddl(database: str, table: str) -> str:
    return f"""CREATE TABLE {identifier(database)}.{identifier(table)} (
        {", ".join(identifier(c) + " " + TYPES[c] for c in DESTINATION)}
    ) ENGINE=MergeTree PARTITION BY month
    ORDER BY (month, ifNull(user_id,''), ifNull(user_session,''),
              ifNull(event_time_utc,toDateTime64(0,6,'UTC')), ifNull(product_id,''))
    COMMENT '{MARKER}'"""


def json_select() -> str:
    fields = [
        f"{c} := {'cast(price AS DECIMAL(18,2))' if c == 'price' else c}"
        for c in (*ORIGINAL, "month")
    ]
    fields += [
        "event_time_utc := strftime(event_time_utc,'%Y-%m-%d %H:%M:%S.%f')",
        "price_raw := price",
    ]
    return "SELECT to_json(struct_pack(" + ", ".join(fields) + ")) FROM raw_events"
