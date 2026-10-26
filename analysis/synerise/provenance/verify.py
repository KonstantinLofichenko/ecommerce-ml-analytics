"""Read-only provenance and clock diagnostics on the already downloaded Synerise archive."""

import hashlib
import json
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent
RESEARCH = ROOT.parent
SOURCE = Path("data/external/synerise/source")
ARCHIVE = SOURCE.parent / "synerise_dataset.tar.gz"
EVENTS = ("page_visit", "search_query", "add_to_cart", "remove_from_cart", "product_buy")
REFERENCE = dict(zip(EVENTS, (150713186, 9571258, 5235882, 1697891, 1682296), strict=True))


def digest_stream(source):
    digest = hashlib.sha256()
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def rows(c, sql, params=None):
    cursor = c.execute(sql, params or [])
    names = [x[0] for x in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def main():
    began = time.monotonic()
    manifest = json.loads((RESEARCH / "download-manifest.json").read_text())
    previous = json.loads((RESEARCH / "results.json").read_text())
    result = {
        "date": "2026-10-21",
        "archive": str(ARCHIVE),
        "original_url": "https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz",
        "memory_limit": "2GB",
        "threads": 2,
        "files": {},
        "archive_members": [],
        "queries": [],
    }

    def save():
        (ROOT / "verification.json").write_text(json.dumps(result, indent=2, default=str) + "\n")

    with ARCHIVE.open("rb") as source:
        result["archive_sha256"] = digest_stream(source)
    assert result["archive_sha256"] == manifest["archive_sha256"]
    assert ARCHIVE.stat().st_size == manifest["archive_bytes"]
    expected = {m["name"]: m for m in manifest["members"]}
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        for member in archive:
            if not member.isfile():
                raise ValueError("Unexpected non-file member")
            assert member.name in expected
            stream = archive.extractfile(member)
            assert stream is not None
            with stream:
                digest = digest_stream(stream)
            assert digest == expected[member.name]["sha256"]
            assert member.size == expected[member.name]["bytes"]
            result["archive_members"].append(
                {
                    "name": member.name,
                    "bytes": member.size,
                    "mtime_epoch": member.mtime,
                    "mtime_utc": datetime.fromtimestamp(member.mtime, UTC).isoformat(),
                    "sha256_matches_extraction": True,
                }
            )
    assert len(result["archive_members"]) == len(expected) == 6
    save()
    with duckdb.connect() as c:
        c.execute("SET memory_limit='2GB'")
        c.execute("SET threads=2")
        c.execute("SET preserve_insertion_order=false")

        def execute(label, sql):
            start = time.monotonic()
            data = rows(c, sql)
            result["queries"].append(
                {
                    "name": label,
                    "sql": sql,
                    "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                    "seconds": time.monotonic() - start,
                    "status": "executed",
                }
            )
            return data

        for name in (*EVENTS, "product_properties"):
            print(f"Checking {name}", flush=True)
            path = SOURCE / f"{name}.parquet"
            with path.open("rb") as source:
                digest = digest_stream(source)
            assert digest == expected[path.name]["sha256"]
            fileinfo = {"sha256": digest, "bytes": path.stat().st_size}
            result["files"][name] = fileinfo
            c.execute(f"CREATE OR REPLACE TEMP VIEW source AS SELECT * FROM read_parquet('{path}')")
            fileinfo["parquet_metadata"] = rows(
                c, "SELECT * EXCLUDE(file_name) FROM parquet_file_metadata(?)", [str(path)]
            )
            schema = rows(c, "DESCRIBE source")
            keys = ",".join('"' + x["column_name"] + '"' for x in schema)
            fileinfo["row_count"] = execute(name + "_count", "SELECT count(*) AS n FROM source")[0][
                "n"
            ]
            assert fileinfo["row_count"] == previous[name + "_nulls"][0]["rows"]
            # Fixed Parquet row-group size is checked, not silently assumed.
            sizes = rows(
                c,
                "SELECT DISTINCT row_group_id,row_group_num_rows FROM parquet_metadata(?) "
                "ORDER BY row_group_id",
                [str(path)],
            )
            assert all(x["row_group_num_rows"] == 1048576 for x in sizes[:-1])
            fileinfo["row_groups"] = len(sizes)
            fingerprint_sql = f"""SELECT file_row_number//1048576 AS segment,count(*) AS n,
                sum(hash({keys})::HUGEINT) AS sum_hash,bit_xor(hash({keys})) AS xor_hash
                FROM read_parquet('{path}',file_row_number=true)
                GROUP BY segment ORDER BY segment"""
            fingerprints = execute(name + "_segments", fingerprint_sql)
            signatures = {}
            duplicates = []
            for group in fingerprints:
                sig = (group["n"], group["sum_hash"], group["xor_hash"])
                if sig in signatures:
                    duplicates.append([signatures[sig], group["segment"]])
                signatures[sig] = group["segment"]
            fileinfo["row_group_fingerprints"] = fingerprints
            fileinfo["equal_row_group_fingerprint_pairs"] = duplicates
            if name in EVENTS:
                fileinfo["time_bounds"] = execute(
                    name + "_bounds",
                    """SELECT
                    min(TRY_CAST(timestamp AS TIMESTAMP)) AS first_ts,
                    max(TRY_CAST(timestamp AS TIMESTAMP)) AS last_ts,
                    count_if(TRY_CAST(timestamp AS TIMESTAMP) IS NULL) AS unusable_ts
                    FROM source""",
                )[0]
                assert (
                    fileinfo["time_bounds"]["first_ts"].isoformat(" ")
                    == previous[name + "_profile"][0]["first_ts"]
                )
                assert (
                    fileinfo["time_bounds"]["last_ts"].isoformat(" ")
                    == previous[name + "_profile"][0]["last_ts"]
                )
                fileinfo["hourly_by_date"] = execute(
                    name + "_hourly",
                    """SELECT
                    CAST(timestamp AS DATE) AS date,
                    date_part('hour',CAST(timestamp AS TIMESTAMP)) AS hour,
                    count(*) AS n FROM source GROUP BY date,hour ORDER BY date,hour""",
                )
                fileinfo["seconds"] = execute(
                    name + "_seconds",
                    """SELECT
                    date_part('second',CAST(timestamp AS TIMESTAMP)) AS second,count(*) AS n
                    FROM source GROUP BY second ORDER BY second""",
                )
                fileinfo["minute_of_hour"] = execute(
                    name + "_minutes",
                    """SELECT
                    date_part('minute',CAST(timestamp AS TIMESTAMP)) AS minute,count(*) AS n
                    FROM source GROUP BY minute ORDER BY minute""",
                )
                fileinfo["weekdays"] = execute(
                    name + "_weekday",
                    """SELECT
                    date_part('isodow',CAST(timestamp AS TIMESTAMP)) AS iso_weekday,
                    count(*) AS n,count(DISTINCT CAST(timestamp AS DATE)) AS observed_days
                    FROM source GROUP BY iso_weekday ORDER BY iso_weekday""",
                )
                fileinfo["row_group_time_ranges"] = execute(
                    name + "_segment_ranges",
                    f"""SELECT
                    file_row_number//1048576 AS segment,
                    min(timestamp) AS first_ts,max(timestamp) AS last_ts
                    FROM read_parquet('{path}',file_row_number=true)
                GROUP BY segment ORDER BY segment""",
                )
                cumulative = 0
                for day in previous[name + "_daily"]:
                    before = cumulative
                    cumulative += day["events"]
                    if before < REFERENCE[name] <= cumulative:
                        fileinfo["reference_prefix_crossing"] = {
                            "source_date": day["date"],
                            "rows_before_day": before,
                            "rows_at_end_of_day": cumulative,
                            "reference": REFERENCE[name],
                        }
                        break
                assert sum(x["n"] for x in fileinfo["hourly_by_date"]) == fileinfo["row_count"]
            save()
    # Recheck after all diagnostics to detect unintended source changes during the run.
    for name, fileinfo in result["files"].items():
        with (SOURCE / f"{name}.parquet").open("rb") as source:
            assert digest_stream(source) == fileinfo["sha256"]
    result.update(
        status="complete",
        source_hashes_match_before_and_after=True,
        seconds=time.monotonic() - began,
    )
    save()
    print("Verification complete", flush=True)


if __name__ == "__main__":
    main()
