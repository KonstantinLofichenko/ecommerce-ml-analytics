"""Produce aggregate CSV and report tables solely from recorded measurements."""

import csv
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
r = json.loads((ROOT / "results.json").read_text())
fields = [
    "source",
    "method",
    "rows",
    "repetition",
    "batch_size",
    "transfer_seconds",
    "preparation_seconds",
    "read_seconds",
    "pipeline_seconds",
    "rows_per_pipeline_second",
    "query_memory_peak",
    "sampled_container_memory_peak",
    "sampled_python_rss_peak",
    "compressed_bytes",
    "parts",
    "cpu_seconds",
    "errors",
    "retries",
    "reconciled",
]
with (ROOT / "trials.csv").open("w") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for t in r["trials"]:
        logs = [x for x in t["query_logs"] if x]
        writer.writerow(
            {
                **{k: t[k] for k in fields if k in t},
                "query_memory_peak": max(int(x["memory_usage"]) for x in logs),
                "sampled_container_memory_peak": max(
                    x["CGroupMemoryUsed"] for x in t["resource_samples"]
                ),
                "sampled_python_rss_peak": max(x["python_rss"] for x in t["resource_samples"]),
                "compressed_bytes": t["storage"]["compressed_bytes"],
                "parts": t["storage"]["parts"],
                "cpu_seconds": sum(int(x["cpu_user_us"]) + int(x["cpu_system_us"]) for x in logs)
                / 1e6,
                "reconciled": t["integrity"]["exact_multiset_match"],
            }
        )
lines = ["| Source | HTTP Parquet rows/s | ArrowStream rows/s |", "| --- | ---: | ---: |"]
for source in r["source_hashes"]:
    values = []
    for method in ("http_parquet", "arrow_stream"):
        values.append(
            median(
                t["rows_per_pipeline_second"]
                for t in r["trials"]
                if t["source"] == source and t["rows"] == 50000 and t["method"] == method
            )
        )
    lines.append(f"| {source} | {values[0]:,.0f} | {values[1]:,.0f} |")
(ROOT / "comparison.md").write_text("\n".join(lines) + "\n")
