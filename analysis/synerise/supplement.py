"""Additional selective point-in-time coverage and timestamp diagnostics."""

import json
import runpy
from pathlib import Path

import duckdb

module = runpy.run_path(str(Path(__file__).with_name("run.py")))
query, setup = module["query"], module["setup"]
with duckdb.connect() as c:
    c.execute("SET memory_limit='2GB'")
    c.execute("SET threads=2")
    setup(c, Path("data/external/synerise/source").resolve())
    c.execute("""CREATE TEMP TABLE snapshots AS
        SELECT TIMESTAMP '2022-11-01' AS snapshot""")
    result = {
        "features": query(c, Path(__file__).with_name("sql").joinpath("features.sql").read_text())
    }
    result["timestamp_precision"] = query(
        c,
        """SELECT kind,count(*) AS events,
        count_if(date_part('second',ts)%5=0) AS seconds_multiple_of_5,
        count_if(date_part('second',ts)=0) AS minute_aligned
        FROM events GROUP BY kind ORDER BY kind""",
    )
    result["purchase_frequency"] = query(
        c,
        """SELECT purchase_days,count(*) AS customers FROM (
        SELECT client_id,count(DISTINCT CAST(ts AS DATE)) AS purchase_days
        FROM product_buy GROUP BY client_id) GROUP BY purchase_days ORDER BY purchase_days""",
    )
    result["event_overlap"] = query(
        c,
        """SELECT p.kind,count(DISTINCT p.client_id) AS clients,
        count(DISTINCT p.client_id) FILTER (WHERE b.client_id IS NOT NULL) AS also_purchasers
        FROM events p LEFT JOIN (SELECT DISTINCT client_id FROM product_buy) b USING(client_id)
        GROUP BY p.kind ORDER BY p.kind""",
    )
    result["tie_overlap"] = query(
        c, Path(__file__).with_name("sql").joinpath("tie_overlap.sql").read_text()
    )
    result["customer_overlap"] = query(
        c, Path(__file__).with_name("sql").joinpath("overlap.sql").read_text()
    )
Path("analysis/synerise/supplement.json").write_text(
    json.dumps(result, indent=2, default=str) + "\n"
)
print("Supplement completed")
