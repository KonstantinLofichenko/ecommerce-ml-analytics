# Bounded benchmark protocol

Runtime safety is a gate, not permission to start Docker or raise limits.

`benchmark.py --execute-isolated-poc` requires existing reachable ClickHouse,
no active merges/other queries, >=256 MiB cgroup headroom and server RSS below
1200 MiB. Each request is capped at 64 MiB and one thread. These are conservative
POC gates, not a guarantee against other applications starting work concurrently.
Abort rather than bypass the gate. No production data writes or credential changes.

The script uses a UUID/comment-owned database; only that exact database can be
cleaned up, after verifying its UUID and comment. It never cleans any pre-existing
table. A surviving test database after interruption must be inspected against its
saved manifest before explicit cleanup, never matched with a wildcard DROP.

At most 10,000 first-row-group rows each of page_visit/add_to_cart/product_buy/
product_properties are selected. Source SHA must match. Native HTTP Parquet and
PyArrow-to-ArrowStream use the same bounded sample, equivalent schema/codecs and
synchronous gzip HTTP transport. Alternating method order reduces a simple order
bias; one sample per method is still exploratory and not a production benchmark.

Record sample preparation, PyArrow preparation, insertion/ack time, transport bytes,
query_id, query_log memory_usage, resident/cgroup samples, compressed/part bytes,
row counts and exact typed original-row multiset equality. The Counter operates
only over 10k rows; it is not a full-dataset reconciliation algorithm. Preserve
empty/Unicode strings and signed 64-bit identifiers; compare duplicate multiplicity,
not just distinct rows. Validate parsed source day and civil-clock seconds against
independent naive Python date arithmetic. No source timestamp is localized.

Before/after: record `ecommerce.raw_events` UUID/count, protected local hashes and
the owned DB cleanup result. Query-log statistics may lag; poll read-only without
FLUSH LOGS or changing server settings. RSS samples are **observed** samples, not a
continuous high-water guarantee. Query memory and Python RSS are separate metrics.
Raw compressed bytes immediately after insertion can change with background merges;
never extrapolate tiny-sample bytes/row into a promised full-corpus size.

Example invocation, only in a safe running environment:

```bash
# Temporary environment; no project dependency changes in this planning phase.
.venv/bin/python -m venv /tmp/synerise-architecture-venv
/tmp/synerise-architecture-venv/bin/pip install 'pyarrow==20.0.0'
PYTHONPATH=src /tmp/synerise-architecture-venv/bin/python \
  analysis/synerise/architecture/benchmark.py --execute-isolated-poc
```

A later acceptance run should add search/remove sources, injected exact duplicate
and timestamp-boundary fixtures, reversed method order, at least three repetitions,
and 10k/50k/250k bounded samples only after resource review. Measure source decoding,
HTTP overhead, server reader/merges, and client peak RSS independently. The small POC
cannot establish sustained full-file throughput or failure-recovery correctness.
