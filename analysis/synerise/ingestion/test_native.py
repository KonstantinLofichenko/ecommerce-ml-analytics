"""Local safety tests; live file() POC evidence is recorded separately."""

import runpy
from pathlib import Path

import pytest

API = runpy.run_path(str(Path(__file__).with_name("native.py")))


def complete_files():
    return {
        s: {
            "status": "validated",
            "source_hash_reverified": True,
            "destination_aggregate": {"rows": n},
        }
        for s, n in API["EXPECTED"].items()
    }


def test_incomplete_release_cannot_complete():
    files = complete_files()
    files.pop("page_visit")
    with pytest.raises(ValueError):
        API["validate_release"](files)


def test_wrong_count_or_unverified_hash_cannot_complete():
    for change in (
        {"status": "loading"},
        {"source_hash_reverified": False},
        {"destination_aggregate": {"rows": 1}},
    ):
        files = complete_files()
        files["product_buy"].update(change)
        with pytest.raises(ValueError):
            API["validate_release"](files)
    assert API["validate_release"](complete_files()) == 226758312


def test_unknown_source_path_rejected():
    with pytest.raises(ValueError):
        API["source_relation"]("../other_project")


def test_associative_checksums_and_numeric_ranges_ignore_empty_partitions():
    parts = [
        {
            "rows": 2,
            "md5_sum": "17",
            "sha256_sum": "23",
            "sha256_xor": 7,
            "min_sku": "11",
            "max_sku": "20",
            "null_sku": 0,
        },
        {
            "rows": 0,
            "md5_sum": 0,
            "sha256_sum": 0,
            "sha256_xor": 0,
            "min_sku": "0",
            "max_sku": "0",
            "null_sku": 0,
        },
        {
            "rows": 1,
            "md5_sum": "19",
            "sha256_sum": "29",
            "sha256_xor": 3,
            "min_sku": "-2",
            "max_sku": "3",
            "null_sku": 0,
        },
    ]
    combined = API["combine_aggregates"](parts)
    assert combined == {
        "rows": 3,
        "md5_sum": 36,
        "sha256_sum": 52,
        "sha256_xor": 4,
        "min_sku": -2,
        "max_sku": 20,
        "null_sku": 0,
    }
    assert API["combine_aggregates"](list(reversed(parts))) == combined


def test_canonical_encoding_distinguishes_null_empty_unicode_and_signed_values():
    encode = API["canonical_bytes"]
    base = {"sku": -1, "category": 2, "price": 3, "name": "東京"}
    raw = encode("product_properties", base)
    assert raw.endswith(b"V2:-1V1:2V1:3V6:" + "東京".encode())
    assert encode("product_properties", {**base, "name": None}) != encode(
        "product_properties", {**base, "name": ""}
    )
    sql = API["aggregate_sql"]("product_properties", "test")
    assert "MD5(" in sql and "SHA256(" in sql and "GROUP BY" not in sql
