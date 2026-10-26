"""Independent boundary/grouping/sequence checks for Synerise research SQL."""

from pathlib import Path
from string import Template

import duckdb

SQL = Path(__file__).with_name("sql")


def rows(c, name):
    cursor = c.execute((SQL / f"{name}.sql").read_text())
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def test_purchase_definitions_and_half_open_targets():
    with duckdb.connect() as c:
        c.execute("CREATE TABLE product_buy(client_id BIGINT,ts TIMESTAMP,sku BIGINT)")
        c.execute("""INSERT INTO product_buy VALUES
          (1,'2025-01-31 23:59:59.999999',10),(1,'2025-02-01',11),
          (2,'2025-01-20',10),(2,'2025-02-15',11),
          (3,'2025-02-01',10),
          (4,'2025-01-20',10),(4,'2025-01-20',11)""")
        c.execute("CREATE VIEW events AS SELECT * FROM product_buy")
        c.execute("CREATE TABLE snapshots AS SELECT TIMESTAMP '2025-02-01' AS snapshot")
        counts = {r["definition"]: r for r in rows(c, "purchases")}
        assert counts["A_event"]["repeat_purchasers"] == 3
        assert counts["B_timestamp_occasion"]["repeat_purchasers"] == 2
        assert counts["C_purchase_day"]["repeat_purchasers"] == 2
        for r in rows(c, "snapshots"):
            assert (r["eligible"], r["positives"], r["negatives"]) == (3, 1, 2)
            assert r["minimum_prior"] >= 1


def test_strict_bounded_funnel_and_same_sku():
    with duckdb.connect() as c:
        for name in ("page_visit", "search_query", "add_to_cart", "product_buy"):
            c.execute(f"CREATE TABLE {name}(client_id BIGINT,ts TIMESTAMP,sku BIGINT)")
        c.execute("INSERT INTO page_visit VALUES (1,'2025-01-01',NULL),(2,'2025-01-01',NULL)")
        c.execute("INSERT INTO search_query VALUES (1,'2025-01-01 01:00:00',NULL)")
        c.execute("""INSERT INTO add_to_cart VALUES
            (1,'2025-01-01 02:00:00',10),(2,'2025-01-01',10)""")
        c.execute("""INSERT INTO product_buy VALUES
            (1,'2025-01-03',11),(1,'2025-01-03',11),(2,'2025-01-02',10)""")

        def execute(days):
            return c.execute(
                Template((SQL / "bounded_funnel.sql").read_text()).substitute(days=days)
            ).fetchone()

        short = execute(1)
        long = execute(7)
        assert short[3] == 1  # page -> cart excludes equal timestamps for customer 2
        assert short[5] == 0  # customer 1 purchase outside one-day bound
        assert long[5] == 1  # duplicate purchase rows do not inflate customers
        assert long[6] == 1  # valid search path
        assert long[7] == 1  # only customer 2 has same-SKU cart -> buy
