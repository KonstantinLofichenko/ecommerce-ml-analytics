# Reproducing the completed portfolio

This guide separates current development setup from the two preserved V4.1 runs.
Finalization checks on **5 November 2026** did not retrain real-data models or rerun
the original holdout. [Check results and remaining limits](reports/project-finalization.md).

## Prerequisites and data boundary

Use Python 3.11 (3.11.16 was used for the experiments), uv and the existing local
Docker services. ClickHouse, dbt models and the original local data are separate
prerequisites: Git does not ship 225 million events or automatically download them.
[Infrastructure](infrastructure.md), [Synerise ingestion](reports/phase-3.5-synerise-bulk-load.md),
[feature builds](customer-features-v4.md), and [dbt operations](dashboard-v1-operations.md)
describe those steps. Data licensing/provenance restrictions still apply.

The feature table is **`synerise_analytics.ml_customer_features`**, not the retired
`ml_customer_features_v4`. All-history V3 summaries support its eligibility/target;
raw events are filtered before feature aggregation. No source refresh is needed
merely to inspect preserved results or run default Python tests.

## Current project environment

```bash
uv sync --locked --extra dev --extra ml
uv run --locked --extra dev --extra ml pytest -q
uv run --locked --extra dev --extra ml ruff check .
uv run --locked --extra dev --extra ml ruff format --check .
```

`uv.lock` provides current dependency resolution; `ml` enables LightGBM and `dev`
enables tests/JupyterLab. On macOS LightGBM's native library requires OpenMP
(`libomp`); the existing installation was reused, not reinstalled during finalization.
The original notebook and its verbatim configuration report have narrow Ruff
exclusions to preserve evidence. Other Python code/tests remain checked.

The notebook's full historical environment was not captured. Current locked
versions cannot prove its original environment: in particular, current uv.lock
pins NumPy 2.5.4 whereas the notebook review environment had NumPy 2.4.6.
See [notebook/kernel setup](../notebooks/README.md). Use a scratch copy for any
separately authorized future rerun; do not overwrite the preserved notebook.

## Historical scripted runtime

The scripted experiment recorded exact versions under `requirements/ml-v41.txt`.
Those core runtime pins differ from the current notebook/development lock.
Use a **separate environment**, and do not combine `uv run --locked` automatic
synchronization with a historical pinned environment: it can replace those pins.

```bash
uv venv .venv-scripted --python 3.11
uv pip install --python .venv-scripted/bin/python -e '.[dev,ml]' \
  -r requirements/ml-v41.txt
.venv-scripted/bin/python -m pytest -q
.venv-scripted/bin/python scripts/train_repeat_purchase.py --help
```

These commands were checked in an isolated `/tmp/ecommerce-portfolio-repro` environment
using Python 3.11.16; the project's existing .venv and lock were not synchronized.
The historical pins cover the execution-time ML runtime, not every current
Jupyter/dev dependency or native system library. Installing dev extras adds the
current development tools within project constraints; it does not reconstruct an
unrecorded historical notebook environment.

Only after explicit authorization for a new frozen-protocol reproduction:

```bash
.venv-scripted/bin/python scripts/train_repeat_purchase.py \
  --output data/processed/phase-4.1/NEW_RUN_DIRECTORY
```

A fresh directory is required. Existing outputs are refused. The optional `--report`
argument renders an aggregate Markdown report, but historical reports should not
be overwritten. The runner reads private `.env` settings with the project's
existing authenticated HTTP client, fits only training rows and writes no predictions
to ClickHouse or Metabase. Never pass passwords in command-line URLs or print `.env`.
Joblib models must be trusted and loaded in the compatible environment.

The original artifacts under `data/processed/phase-4.1/initial-2026-10-30/` include
three models, logistic preprocessing, `selection.json` and aggregate `metrics.json`.
They are ignored by Git; the [scripted report](reports/phase-4.1-repeat-purchase.md)
retains configuration, results and dataset SHA-256. No customer-level predictions
or complete feature export are required in version control.

## Non-training checks used in finalization

- Imported the CLI with `--help` under the historical pinned runtime.
- Ran Python tests with synthetic fixtures, including tiny synthetic model fits;
  these are implementation tests, not new customer experiments.
- Called the existing `load_dataset()` and `chronological_split()` functions only:
  validated 547,914 rows, 74,781 positives, approved class distributions and maturity.
  The ordered feature-stream SHA-256 matched the original metrics record.
- Loaded the original trusted joblib files and predicted only two invented seven-
  feature vectors. No original evaluation rows were scored.
- Parsed dbt and ran tests against existing tables using the configured catalog
  target and one thread. No `dbt run`, `dbt build`, migration or service recreation.

With the existing authorized credentials privately exported, dbt checks are:

```bash
export CLICKHOUSE_DATABASE=synerise_analytics
export CLICKHOUSE_HOST=127.0.0.1
export CLICKHOUSE_PORT=18123
# CLICKHOUSE_USER and CLICKHOUSE_PASSWORD are already privately configured.
.venv-dbt/bin/dbt parse --project-dir dbt --profiles-dir dbt --target catalog
.venv-dbt/bin/dbt test --project-dir dbt --profiles-dir dbt --target catalog --threads 1
```

In restricted environments Matplotlib may emit a cache-directory warning during
LightGBM import. If needed, set `MPLCONFIGDIR` to a writable ignored scratch directory;
this is an environment/cache setting, not a model change.

## What reproduction does not establish

Re-executing code is distinct from proving uninterrupted tracking, true UTC,
first-ever purchase, reliable orders or prospective model value. The target stays
a later-calendar-date repeat outcome; counts are original raw event counts and
labels are not order counts. The one-week historical test is now known evidence,
not a reusable untouched tuning set. Notebook full-population EDA exposed test
labels. Any future optimization needs a fresh holdout and a separately approved
protocol. Rolling evaluation, new features, deployment and orchestration remain
outside this completed milestone.
