"""Generate continuation tables from measured aggregate results, never event rows."""

import csv
import json

from native import EXPECTED, ROOT

r = json.loads((ROOT / "results.json").read_text())
rows = []
performance = []
for source, expected in EXPECTED.items():
    f = r["files"].get(source, {})
    src, dst = f.get("source_aggregate", {}), f.get("destination_aggregate", {})
    rows.append(
        {
            "source": source,
            "expected": expected,
            "status": f.get("status", "not_attempted"),
            "retained_rows": r["validated_destination_counts"].get(source, 0),
            "source_rows": src.get("rows"),
            "destination_rows": dst.get("rows"),
            "source_md5_sum": src.get("md5_sum"),
            "destination_md5_sum": dst.get("md5_sum"),
            "source_sha256_sum": src.get("sha256_sum"),
            "destination_sha256_sum": dst.get("sha256_sum"),
            "source_sha256_xor": src.get("sha256_xor"),
            "destination_sha256_xor": dst.get("sha256_xor"),
            "source_file_sha256": f.get("source_sha256"),
            "all_aggregate_checks_matched": bool(src) and src == dst,
            "provenance_bad_rows": f.get("provenance_clock", {}).get("bad"),
        }
    )
    if f.get("status") == "validated":
        performance.append(
            {
                "source": source,
                "rows": expected,
                **{
                    k: f[k]
                    for k in (
                        "insert_seconds",
                        "total_seconds",
                        "reconciliation_seconds",
                        "rows_per_insert_second",
                        "query_memory_peak",
                        "errors",
                        "retries",
                    )
                },
                **f["resources"],
                "parts": f["storage"]["parts"],
                "bytes_on_disk": f["storage"]["bytes_on_disk"],
                "compressed_bytes": f["storage"]["compressed_bytes"],
            }
        )
for name, data in [("reconciliation.csv", rows), ("performance.csv", performance)]:
    with (ROOT / name).open("w") as out:
        w = csv.DictWriter(out, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
lines = ["| Source | Required | Retained | State |", "| --- | ---: | ---: | --- |"]
for row in rows:
    lines.append(
        f"| {row['source']} | {row['expected']:,} | {row['retained_rows']:,} | {row['status']} |"
    )
(ROOT / "counts.md").write_text("\n".join(lines) + "\n")
lines = [
    "| Source | Insert seconds | Checksum seconds | File elapsed seconds | "
    "Insert rows/s | Query peak MiB |",
    "| --- | ---: | ---: | ---: | ---: | ---: |",
]
for f in performance:
    lines.append(
        f"| {f['source']} | {f['insert_seconds']:.3f} | {f['reconciliation_seconds']:.3f} | "
        f"{f['total_seconds']:.3f} | {f['rows_per_insert_second']:,.0f} | "
        f"{f['query_memory_peak'] / 1024**2:.1f} |"
    )
(ROOT / "performance.md").write_text("\n".join(lines) + "\n")
