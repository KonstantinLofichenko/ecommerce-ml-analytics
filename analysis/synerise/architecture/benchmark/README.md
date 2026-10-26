# Phase 3.4.1 bounded ingestion experiment

**INCONCLUSIVE.** See [report](../../../../docs/reports/phase-3.4.1-synerise-ingestion-benchmark.md).
65 successful trials / 3,140,000 reconciled source rows; one global server-memory
abort. No production ingestion or migration. `results.json` is the complete evidence;
`trials.csv` gives every completed trial's metrics, `comparison.md` the balanced 50k
comparison. `initial-ddl-failure.json` preserves the cleaned-up initial schema failure.

`run.py` reuses `../schema.py` and the project's HTTP client. It verifies configured
8/6 GiB limits, health, two CPUs, idle workload and protected file hashes before
creating an exact UUID/comment-owned temporary database. One writer, 10k rows per
request, one data request in flight, no insert retries. A concurrent read-only
monitor collects asynchronous memory/merges/disk and Python RSS. Every completed
trial is reconciled then dropped; the database is cleaned in `finally` only after
ownership verification. The improved monitor additionally checks MemoryTracking
before each trial; that tracker was absent from the originally executed monitor.
The original measurements are retained unchanged; do not claim they measured it.

Source records: first N rows of physical row group 0, N=10k/50k/100k, all six
Parquet files, PyArrow `iter_batches(batch_size=10000,row_groups=[0],use_threads=False)`.
Each size/source uses two repetitions with reversed transport order. Parquet
payloads are reencoded in bounded buffers with Snappy; ArrowStream uses the same
source fields/batches. Both travel over HTTP using the existing client's gzip1.
Source decoding, serialization and HTTP transfer are timed separately. Monitor,
Python-row materialization, DDL, validation and cleanup are excluded from reported
pipeline throughput. Monitored wall time is separately recorded. JSON raw rows are
held only for bounded reconciliation (<=100k); never exported to artifacts.

The first benchmark stopped immediately on code 241; the incomplete trial was not
replayed, and its acknowledged/uncertain partial rows were discarded with the owned
database. Only the completed trials have checksums and timing claims. `finalize.py`
reads naturally flushed logs and runs tiny guarded recovery cases with `guards.py`.
It deliberately discards a real successful insert response by raising ConnectionError
at the controller boundary, refuses replay, verifies old rows, and restarts into a
new attempt/table. This is a controlled response-discard test, not a network fault
or production publication transaction test. Checksums/incomplete publication are
actual guard checks, without publishing any production table.

Prerequisites: existing project environment/client configuration and the already
created `/tmp/synerise-architecture-venv` with **PyArrow 20.0.0**, Python 3.11.16.
No project dependency or service configuration change. If that environment no longer
exists, provision a separate research environment with the same versions; do not
add PyArrow to production dependencies solely to rerun this experiment.

Reproduction from repo root (performance rerun requires review of the memory abort;
do not automatically execute this as a migration step):

```bash
PYTHONPATH=src /tmp/synerise-architecture-venv/bin/python \
  analysis/synerise/architecture/benchmark/run.py --execute-isolated-benchmark
# After the performance process exits and memory headroom has recovered:
PYTHONPATH=src /tmp/synerise-architecture-venv/bin/python \
  analysis/synerise/architecture/benchmark/finalize.py
python3 analysis/synerise/architecture/benchmark/summarize.py
.venv/bin/pytest -q analysis/synerise/architecture/test_design.py \
  analysis/synerise/architecture/benchmark/test_guards.py
.venv/bin/ruff check analysis/synerise/architecture
.venv/bin/ruff format --check analysis/synerise/architecture
```

Runs replace local result artifacts; archive them first to preserve an experiment.
`finalize.py` is part of this failed-run investigation and conservatively records
INCONCLUSIVE. It is not a general production finalizer. CPU query time comes from
ProfileEvents; sampled memory is not a continuous peak. Python `ru_maxrss` is bytes
on macOS and a process-lifetime high-water mark; it includes reconciliation and
allocator retention, so per-trial sampled RSS and lifetime maxima are distinguished.
Resource metrics can lag; no scaling estimate is a full-load guarantee.
