"""Boundary checks for the independent generator assessment's label calculations."""

import runpy
from pathlib import Path

import duckdb

snapshot_counts = runpy.run_path(str(Path(__file__).with_name("evaluate.py")))["snapshot_counts"]


def test_snapshot_cutoffs_and_identity_exclusion():
    with duckdb.connect() as connection:
        connection.execute(
            "CREATE TABLE events(name VARCHAR, pseudo VARCHAR, uid VARCHAR, ts TIMESTAMP)"
        )
        connection.execute("""
            INSERT INTO events VALUES
              ('purchase','a','u1','2025-01-31 23:59:59.999999'),
              ('purchase','a','u1','2025-02-01'),
              ('purchase','b',NULL,'2025-01-20'),
              ('purchase','b',NULL,'2025-02-15'),
              ('purchase','c','u3','2025-02-01'),
              ('page_view','b',NULL,'2025-02-02')
        """)
        connection.execute("CREATE TABLE orders(customer_id VARCHAR, ts TIMESTAMP)")
        result = snapshot_counts(connection)
    first = [r for r in result if str(r["snapshot"]) == "2025-02-01 00:00:00"]
    pseudo = next(r for r in first if r["identity"] == "pseudo_id")
    login = next(r for r in first if r["identity"] == "observed_login_id")
    assert (pseudo["eligible"], pseudo["positives"], pseudo["negatives"]) == (2, 1, 1)
    assert (login["eligible"], login["positives"]) == (1, 1)
    assert pseudo["minimum_prior_purchases"] == 1
