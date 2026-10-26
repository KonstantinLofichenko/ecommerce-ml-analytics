# Synerise RecSys 2025 feasibility research

Original Synerise events, not the competition's selected/preprocessed population.
Research only: no production database, Docker or ML access. See the
[assessment](../../docs/reports/phase-3.3-synerise-assessment.md).

## Provenance and attribution

Universal Behavioral Modeling Dataset © 2025 Synerise SA, licensed under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
Sources: [official dataset](https://recsys.synerise.com/data-set),
[license notice](https://recsys.synerise.com/summary),
[organizer code](https://github.com/Synerise/recsys2025), inspected commit
`e91c1a62f84611151a399ce157e6031a4a73618f` (MIT for code, distinct from data license).
Changes: analytical aggregates and explicitly labeled derived purchase occasions;
original source files preserved, no deduplication applied. No endorsement implied.
The NonCommercial condition remains applicable: public visibility alone does not
settle whether a portfolio's particular use is noncommercial. Assess commercial,
sponsored or paid reuse separately; code's MIT license does not relicense the data.
Raw client records are not versioned or published here.

## Download and extraction

Before download, this machine had ~1.4 TiB free and 128 GiB physical RAM. The
source was not already in this project's data directories. Official public URL:
`https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz`.
No account/key required. HEAD returned 2,062,884,710 bytes and last-modified
12 November 2025. Archive inspection found exactly six regular Parquet files,
2,603,781,937 bytes total. Archive + extracted sources require ~4.35 GiB; reserve
additional scratch space (runner caps spill at 80 GB). Archives are preserved.
`download-manifest.json` records archive and per-file SHA-256 and member inventory.
No publisher checksum was supplied; the recorded hash pins this downloaded version,
not independent authenticity verification.

The download used `curl --fail --location --retry 3 --continue-at -` to an isolated
ignored `data/external/synerise/` directory. No interrupted transfer occurred, so
server resume behavior was not separately verified.

```bash
mkdir -p data/external/synerise
curl --fail --location --retry 3 --continue-at - \
  --output data/external/synerise/synerise_dataset.tar.gz \
  https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz
.venv/bin/python analysis/synerise/inspect_archive.py \
  --archive data/external/synerise/synerise_dataset.tar.gz \
  --destination data/external/synerise/source \
  --manifest analysis/synerise/download-manifest.json
```

The extractor inventories all members before creating a fresh destination, rejects
links, absolute/traversal paths and missing/duplicate source files, and bounds selected
size to 100 GiB. It refuses existing extraction destinations and writes files with
exclusive creation. On a completed extraction, reuse the preserved source files;
do not rerun extraction into that directory. Inspect current free space before any
new download/extraction. No automatic deletion is performed.

## Reproduce analysis

Uses existing project DuckDB; no added package. Raw Parquet is scanned directly,
only small aggregate results enter Python. SQL in `sql/` is SELECT/CTE only;
Python creates disposable views/tables inside a temporary research database,
never the existing reference file. Work memory is 2 GB / two threads; spill capped
at 80 GB. Partitioning by `hash(client_id)` preserves exact same-client groups.
DuckDB version is recorded; hash assignment need not be stable between versions,
but summing complete partitions preserves the same exact aggregates.

```bash
.venv/bin/python analysis/synerise/run.py
.venv/bin/python analysis/synerise/supplement.py
.venv/bin/python analysis/synerise/report.py
.venv/bin/python -m pytest analysis/synerise/test_research.py -q
.venv/bin/ruff check analysis/synerise
.venv/bin/ruff format --check analysis/synerise
```

`run.py --resume` reuses completed identical named query text in `results.json`.
Use it only with the same source-file hashes from the manifest; it does not establish
that a changed dataset is equivalent. A fresh run without `--resume` recalculates all
results. The complete executed SQL, text hashes and per-query elapsed times are in
`results.json`; temporary customer partition aggregation is defined in `run.py`.
The first unpartitioned page-duplicate attempt exceeded 2 GB; the final runner uses
32 partitions for page duplicates/customer histories and 16 for funnels.

`schema`/`nulls`/`profile`/`daily`/`monthly`/`duplicates` result blocks are full-source
measurements. Nullability in DESCRIBE is permissive schema nullability, not observed
missingness. Approximate client counts are diagnostics; decisions use exact counts.
Supplement results measure historical feature coverage at the observed November 1,
2022 cutoff, timestamp rounding, purchase-day distribution and cross-event overlap.

## Analytical definitions

Timestamps are parsed without a timezone conversion: source timezone is undocumented.
Snapshot times are **source-clock midnight**, pending timezone confirmation; do not
claim measured UTC cutoffs. Invalid/null times cannot establish chronology. No actual
sessions, orders, currency amounts, product-page mapping, checkout or payment steps
are invented. `price` is a 0–99 bucket, not revenue. URL IDs cannot join to SKU.
Quantized name/query embeddings are whitespace-separated integer-vector strings;
they are not readable search terms or unquantized semantic vectors.

Purchases: A retains every event; B groups exact `(client_id, timestamp)` occasions;
C groups client/calendar date. They are signals/heuristics, not reconstructed orders.
Duplicates remain raw. At source-midnight snapshots, A/B/C binary labels must agree
because grouping within the same instant/day does not move a purchase across any
boundary. Their repeat-frequency counts can differ sharply. A horizon ending on a
non-midnight boundary would need separately specified day-group semantics.

Funnel presence is cumulative per client; strict funnels use strictly increasing
times and count each client once. Search is evaluated as optional, in a separate
four-stage path. The ASOF chain selects latest strictly preceding stages: associated
page anchors are nondecreasing, so if the most recent valid chain is too old, no
older chain can satisfy the same bound. Bounds are from initial page to each stage,
not a fresh horizon after every step. Same-SKU cart-to-buy is separate; page and
search events have no defensible SKU mapping. Exact ties cannot prove an ordered
transition. `window_days=-1` means full observed history, not a real session.

Snapshot dates are the last four fully observed month starts at least two calendar
month boundaries after the source's first month. Train the first two, validate the
third, hold out the fourth in a future modeling task. Full coverage is conditional
on source continuity; first/last events alone cannot prove no logging outages.
Cohorts are ever-purchasers and nested, so pairwise overlap equals the earlier
eligible count. Features must filter events `< cutoff` before aggregating. Labels
alone use `[cutoff, cutoff+14 days)`. Property attributes lack version timestamps;
point-in-time availability cannot be established from the static file.
