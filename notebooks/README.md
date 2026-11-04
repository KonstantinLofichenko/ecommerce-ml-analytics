# Repeat-purchase research notebooks

[`01_repeat_purchase_exploration.ipynb`](01_repeat_purchase_exploration.ipynb)
preserves the interactive V4.1 baseline. Its saved outputs were inspected on
**4 November 2026**; no cells were rerun, cleared, reordered or edited.
See [notebook baseline evidence](../docs/ml_baseline_v4_1.md) for configurations,
metrics, permutation importance, ablation, calibration and review limitations.

The [earlier scripted V4.1 experiment](../docs/reports/phase-4.1-repeat-purchase.md)
is a **different run**: different preprocessing/model settings and metrics. Its
CLI is not an exact reproduction of this notebook. Preserve both records.

## Environment and kernel

From the repository root, for an explicitly authorized future reproduction:

```bash
# Separate ignored environment: preserves the existing .venv.
export UV_PROJECT_ENVIRONMENT=.venv-notebook
uv sync --locked --extra dev --extra ml
uv run --locked --extra dev --extra ml python -m ipykernel install --user \
  --name ecommerce-ml-notebook --display-name "Python (ecommerce-ml notebook)"
uv run --locked --extra dev --extra ml jupyter lab --notebook-dir=.
```

Select **Python (ecommerce-ml notebook)** in JupyterLab's kernel selector. The
preserved notebook metadata says `Python 3 (ipykernel)` / `python3`; that generic
name alone does not prove the interpreter is the project environment. Check
`import sys; print(sys.executable)` in a separate scratch notebook or console;
it should point into `.venv-notebook`.

The existing pyproject already declares clickhouse-connect, pandas/scikit-learn,
LightGBM (`ml` extra), and JupyterLab/ipykernel/Matplotlib (`dev` extra). No dependency
changes were made in this documentation task. On macOS, LightGBM requires a usable
OpenMP runtime (the preceding scripted experiment installed Homebrew `libomp`).

`uv lock --check --offline` passed during this review. However, the saved notebook
records only Python 3.11.16 and Matplotlib 3.11.2 explicitly, not a complete historical
package manifest. The current lock has NumPy 2.5.4 while the reviewed installed
`.venv` has NumPy 2.4.6. Locked setup is a reproducible **current environment**, not
proof that it matches the notebook's original execution environment. Do not change
this lock or claim bitwise historical reproduction based solely on it.

## ClickHouse access

The connection cell uses `clickhouse_connect.get_client`, `host="localhost"`,
`port=18123`, `username="ecommerce_app"`, and an interactive **`getpass()`** password
prompt. It does not read `.env` automatically. Obtain the existing password locally;
do not paste it into a code cell, URL, shell command, Markdown or saved output.
Use the existing authorized account; no credentials or grants need changing.

The local ClickHouse service must be reachable and
`synerise_analytics.ml_customer_features` must already exist. The notebook reads
that compact feature table, not the full raw event dataset. Preserve the existing
547,914-customer/74,781-positive snapshot for numerical comparison. Keep Jupyter
local and retain its normal token authentication; do not expose or save its tokens.
The interactive prompt means unattended `nbconvert --execute` is not a drop-in
reproduction command for this unchanged notebook.

## Fresh-kernel execution without overwriting evidence

**Do not rerun the final test or refit models as part of documentation review.**
The following workflow is for a separately authorized future reproduction:

1. Copy the notebook into ignored `scratch/notebooks/` and open the copy. Preserve
   the original file and its saved results. Example preparation:

   ```bash
   mkdir -p scratch/notebooks
   cp -n notebooks/01_repeat_purchase_exploration.ipynb scratch/notebooks/
   ```

2. Select the project kernel, then use **Restart Kernel and Run All Cells**. Answer
   the ClickHouse password prompt interactively. Do not execute cells out of order.
3. The first three cells are a four-row teaching example, not training input.
   Later cells replace `df`: first a ten-row connection preview, then the full
   ordered feature dataset. Verify `Shape: (547914, 11)` before continuing.
4. The seven-feature allowlist defines X; `target_30d` defines y. Date masks create
   the approved three splits and leave temporal gaps unused. Scaling is fitted
   within the logistic pipeline on training only. The LightGBM and six-feature
   ablation fits also use training only; interpretation/calibration use validation.
5. The final two executed cells report seven-feature LightGBM holdout metrics and
   the training-prevalence Brier baseline. Do not use those results for further
   tuning. Save new evidence only in the scratch copy, never over the original.

The notebook lacks executable label-maturity and full dataset-quality assertions;
the [report](../docs/ml_baseline_v4_1.md) documents the audited date arithmetic and
other gaps. The full-population exploratory label summary also includes the test
period before the final test cell. Consequently, the saved workflow is not proof
of a completely sealed holdout. Future tuned work needs a fresh holdout.

## Outputs and Git hygiene

`.env`, `.env.*` (except intentional `.env.example`), `.venv*/`, notebook checkpoints,
`data/processed/`, `scratch/`, Parquet/CSV exports and joblib/pickle models are already
ignored. Put any future generated plots, reports and model artifacts under ignored
`data/processed/phase-4.1/` or `scratch/`; arbitrary PNG/JSON files elsewhere are not
universally ignored. The notebook itself is intentionally reviewable source.

This notebook does not save trained models, raw exports or experiment metrics to
separate files. Its existing outputs include small customer-level previews and two
embedded plots; these were preserved, not silently removed. No currently configured
password/token/secret values were found in the notebook during review. That check
is not a universal secret-detection guarantee; inspect changes before staging.
