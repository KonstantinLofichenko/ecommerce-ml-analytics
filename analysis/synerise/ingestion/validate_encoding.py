"""Verify SQL canonical digests against independent hashlib results, no event transport."""

import hashlib

from native import ROOT, Loader, aggregate_sql, atomic_json, canonical_bytes


def main():
    rows = [
        dict(sku=-9, category=3, price=0, name="東京 🛒"),
        dict(sku=-9, category=3, price=0, name="東京 🛒"),
        dict(sku=None, category=3, price=-1, name=""),
    ]
    relation = (
        "(SELECT CAST(-9 AS Nullable(Int64)) AS sku,toInt64(3) AS category,"
        "toInt64(0) AS price,'東京 🛒' AS name UNION ALL "
        "SELECT CAST(-9 AS Nullable(Int64)),toInt64(3),toInt64(0),'東京 🛒' UNION ALL "
        "SELECT CAST(NULL AS Nullable(Int64)),toInt64(3),toInt64(-1),'')"
    )
    actual = Loader().query(aggregate_sql("product_properties", relation))[0]
    encoded = [canonical_bytes("product_properties", row) for row in rows]
    expected = {
        "md5_sum": sum(int.from_bytes(hashlib.md5(b).digest(), "little") for b in encoded),
        "sha256_sum": sum(
            int.from_bytes(hashlib.sha256(b).digest()[:16], "little") for b in encoded
        ),
        "sha256_xor": 0,
    }
    for b in encoded:
        expected["sha256_xor"] ^= int.from_bytes(hashlib.sha256(b).digest()[24:], "little")
    assert all(int(actual[k]) == v for k, v in expected.items())
    atomic_json(
        ROOT / "encoding-validation.json",
        {
            "fixture": (
                "three synthetic SQL rows: signed IDs, Unicode, empty string, null, duplicate"
            ),
            "reference": "independent Python hashlib and byte encoding",
            "expected": expected,
            "actual": actual,
            "passed": True,
        },
    )
    print("Independent canonical encoding and both digest aggregates passed.")


if __name__ == "__main__":
    main()
