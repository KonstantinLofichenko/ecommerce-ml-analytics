# ML — Repeat Purchase Prediction

Implemented **5 November 2026** on the existing **Synerise funnel analytics**
dashboard, **ID 2**, new **tab ID 8**:
[open the ML tab](http://127.0.0.1:13000/dashboard/2?tab=8).
The collection remains **Konstantin Lofichenko's Personal Collection**, ID 4.
No separate dashboard or Metabase model was created.

## Published data and selection

The four existing `synerise_analytics.ml_*` reporting views are required. They
contain 335,160 predictions, 142 metrics, 35 importance records and 60 calibration
bins. See [publication/provenance](../../ml-results-export.md).
Metabase database **Synerise**, ID 2, recognizes client/count columns as integers,
probabilities/metrics as floats, and identity/provenance as text. Reporting
prediction timestamps are text with the documented computational UTC convention.

Required single-select dashboard filters are **Experiment**, **Model** and
**Dataset Split**. Defaults: `v4.1-scripted-2026-10-30`, `lightgbm`, `test`.
Model choices are linked to Experiment; Split is linked to Experiment and Model.
The API confirms scripted choices `dummy`, `lightgbm`, `logistic`, and notebook
choices `lightgbm`, `logistic`. Original category/minimum/ranking filters and their
mappings remain unchanged; they do not affect ML cards.

Every question is restricted to immutable export
`c498f2518f8708db6ee32c0802b36619a3a44b1b39ba325b4fe5b572422333e7`.
This export identifies exact artifact versions. Dashboard filters then select one
experiment/model/split. Metric questions select one stored metric row directly,
without averaging or summing metric values. Changing the source export requires
an explicit configuration review and reprovisioning, never silent cross-run mixing.

These reusable saved Query Builder questions are intended to run **in this dashboard
with its required identity filters**. Their structured-query parameter defaults are
not independently enforced by Metabase's standalone card-query API. When opening a
saved question separately, explicitly apply Experiment/Model/Split filters before
interpreting or reusing results. The provisioner and validator always supply scope.
Do not run unfiltered standalone metric cards as experiment comparisons.

## Layout and saved questions

A text notice explains provenance and unsupported notebook cards. Below it, six
KPI cards occupy two rows of three; prediction charts are side by side, followed
by full-width importance and calibration charts. All names start with `ML — `.

| ID | Saved question | Implementation / formatting |
| --- | --- | --- |
| 67 | Scored Customers | Query Builder distinct customer count; integer |
| 68 | Actual Repeat Purchase Rate | Query Builder average target; percentage display only |
| 69 | Average Precision (AP) | Query Builder direct saved metric; four decimal places |
| 70 | ROC-AUC | Query Builder direct saved metric; four decimal places |
| 71 | Lift@10% | Query Builder direct saved metric; two decimals and × suffix |
| 72 | Brier Score | Query Builder direct saved metric; four decimal places |
| 73 | Actual Repeat Purchase Rate by Score Decile | Native SQL, bar chart; decile 1 highest; rate fraction formatted as percentage |
| 74 | Prediction Probability Distribution | Query Builder count, 0.05-wide probability bins; bar chart |
| 75 | Feature Importance | Query Builder fields/filter/sort; horizontal bar chart |
| 76 | Probability Calibration | Query Builder expression and fields; observed-rate/reference lines versus mean score |

**Only question 73 uses native SQL**. Query Builder cannot reliably express its
window ranking. [score-deciles.sql](score-deciles.sql) uses `ntile(10)` ordered by
score descending, then signed `client_id` ascending. Ties are reproducible; when a
score straddles the top-decile boundary, this deterministic subset differs from
the scripted report's tie-expected Lift@10%. The saved Lift KPI is never recomputed
from these display deciles. Both scored split sizes divide evenly by ten.

Calibration preserves original equal-width bin boundaries, customer counts, means
and observed rates. Zero-count bins are omitted from the plot only; stored bins
are unchanged. Query Builder's `perfect_calibration` expression copies the mean
score to draw y=x alongside observed rate. No recalibration or evaluation is fitted.

**Small-sample warning:** the highest-probability populated calibration bins
contain very few customers, including one bin with **only one customer** in the
default scripted test selection. Its observed rate of 1.0 is a single outcome;
tail-bin rates are unstable and should not be interpreted as reliable calibration.

Importance uses one compatible method per selection: scripted LightGBM **gain**,
scripted logistic **standardized-log1p coefficients**, or notebook LightGBM
**validation permutation AP drop**. Methods are not combined. Importance is not
causal influence; signed logistic coefficients are not directly comparable to gain.
The Dataset Split filter is intentionally **not mapped to importance**, because
fitted-model importance is not validation/test-specific. The notice explains the
notebook permutation evidence's validation origin. Dummy has no importance rows.

All rate queries return 0–1 values. Percentage scaling is visualization-only.
AP/ROC-AUC are decimal scores, Lift a multiplier, Brier a decimal loss.

## Interpretation and unavailable states

AP summarizes precision/recall ranking and depends on prevalence; ROC-AUC measures
positive-versus-negative ordering. Higher is better for both. Lift@10% is the
selected top-decile positive rate relative to overall prevalence. Brier is mean
squared probability error; lower is better and comparison to a prevalence baseline
matters. Calibration compares predicted probabilities with observed frequencies.

Scripted predictions are regenerated **`artifact_inference`**. Saved metrics and
bins retain **`original_scripted_metrics_json`**. The separate notebook identity
`v4.1-notebook-preserved` exposes rounded **`historical_notebook_saved_output`**,
not independently reproduced results. No scripted scores are substituted for it.

For notebook selections, customer count/rate, deciles, distribution and calibration
show **No results** rather than fabricated zero activity or NaN. The header explains
why. Notebook LightGBM has validation/test summaries; notebook logistic has
validation summaries only. Unsupported model/split combinations remain empty.
Notebook permutation importance remains validation evidence even if Split is test.

The seven-day test, exploratory notebook holdout exposure, calendar-date labels,
and unverified source timezone/continuous coverage remain limitations. These
charts visualize existing frozen evidence; they do not establish deployment value.

## Provisioning and refresh

No previous provisioning script existed. The additive implementation is
[`scripts/provision_metabase_ml.py`](../../../scripts/provision_metabase_ml.py),
with definitions and read-only validation under `src/ecommerce_analytics/reporting/`.
It uses the existing `.env` loader and local `METABASE_URL`, `METABASE_ADMIN` and
`METABASE_ADMIN_PWD` values. Passwords/session tokens are never printed or persisted.
Use existing private credentials; `.env.example` is not an account-creation tool.

Run from the repository root using the verified pinned environment:

```bash
/tmp/ecommerce-portfolio-repro/bin/python scripts/provision_metabase_ml.py
/tmp/ecommerce-portfolio-repro/bin/python scripts/provision_metabase_ml.py --validate-only
```

The temporary Python path is local. For another workstation, use the pinned
[project reproduction environment](../../project-reproduction.md) and substitute
its Python executable. No new dependencies were added.

Provisioning backs up the original dashboard JSON to ignored
`data/processed/metabase-ml/provision/before.json`, validates default scoped queries,
reuses managed saved-question names plus `[managed:ml-dashboard-v1]` descriptions,
and adds/updates only this ML tab and its questions/header/three filter definitions.
Existing tabs, filter definitions and non-ML question/layout settings are compared
before and after. Namespace collisions and concurrent unmanaged edits are refused.
Do not run concurrently with dashboard editing. If interrupted, rerun: stable names
reuse the existing questions rather than duplicate them. No rollback/delete runs
automatically; the backup preserves original content for a reviewed recovery.

Normal dashboard refresh runs read-only queries on published views. This operation
does not train models, export again or rebuild dbt tables. If views disappear from
Metabase, use its normal schema synchronization before provisioning; no schema
sync or configuration restart was needed here.

## Executed validation

- **100 dashboard query checks passed**: ten questions across six scripted and
  four notebook model/split selections. Unsupported evidence returned empty rows.
- All four metric KPIs matched original scripted JSON or hash-pinned notebook
  summaries. Default scripted LightGBM/test: **33,020 customers**, repeat rate
  **13.4464%**, AP **0.2128383090**, ROC-AUC **0.6269064196**, Lift **2.0585585586×**,
  Brier **0.1130196928**.
- Validation population is **78,700**; test **33,020** per scripted model. Every
  decile and histogram population reconciled; test deciles contain 3,302 each.
- All populated calibration bins matched the saved counts/means/rates; their
  reference series equals mean predicted probability. Bin counts reconcile to
  each selected population.
- Experiment-linked Model choices passed both experiments. All queries used
  the dashboard's actual parameter-mapping endpoint, not just standalone SQL.
- Repeated provisioning retained question IDs **67–76**, one ML tab (8) and
  one text notice: **no duplicate questions or dashboard cards**.
- **Four original tabs and 32 original dashboard cards** retained their layouts,
  query definitions, displays, visualization settings, collection placement,
  parameter definitions and mappings. API array-order changes are ignored by ID.
- Read-only preservation checks matched **49 preexisting ClickHouse objects**,
  **41 physical-table counts** and **66 protected file hashes**, including original
  notebook, dbt models/macros, training modules, artifacts and historical metrics.
  Reporting counts remained 335,160 / 142 / 35 / 60.
- **8 new offline tests passed**. Combined with exporter unit tests: **27 passed,
  7 opt-in exporter integration tests skipped**; those live exporter cases were
  already validated in the preceding export task. Ruff and diff checks passed.

Browser access was unavailable, so validation covered live Metabase APIs, Query
Builder execution, visualization configuration and layout metadata. Rendered
pixel-level appearance remains for user review. No source/dbt/model/notebook,
ClickHouse reporting storage, server settings, existing dashboard content,
credentials or Git commits/pushes were changed by this task.

## Visual refinement — 5 November 2026

The saved questions retain their IDs, source queries and filter mappings. AP,
ROC-AUC and Brier use **column-level `decimals=4`**, supported by this Metabase
version; legacy `scalar.decimals` alone was insufficient. Lift uses two decimal
places and ×. Its exact selected scripted LightGBM/test value is
**2.058558558558559 → 2.06×**, distinct from notebook **2.08×**.

Calibration stays in Query Builder: its existing observed and perfect-reference
columns already have the correct data. Both use raw probability units, with
`graph.y_axis.auto_split=false`, `graph.y_axis.auto_range=false`, explicit linear
Y range **0–1**, and decimal column formatting with scale 1. No alternate axis or
percentage multiplier is used. This resolves the configuration without another
native SQL question or any change to bins.

For the default scripted LightGBM/test selection, the high bins reconcile to saved
evidence:

| Probability bin | Customers | Mean probability | Observed rate |
| --- | ---: | ---: | ---: |
| [0.4, 0.5) | 82 | 0.440082 | 0.365854 |
| [0.5, 0.6) | 11 | 0.541082 | 0.272727 |
| [0.6, 0.7) | 1 | 0.627564 | 1.000000 |
| [0.7, 0.8) | 0 | NULL | NULL |
| [0.8, 0.9) | 0 | NULL | NULL |
| [0.9, 1.0] | 0 | NULL | NULL |

The observed rate of 1.0 comes from **one customer**, not strong evidence of
reliable calibration in that tail. Empty bins remain omitted from the plot.

Feature-importance description now explicitly defines default **LightGBM gain**:
summed training split gain for a feature, in raw objective-improvement units,
unnormalized and neither a probability nor a percentage. Other filter selections
retain their existing coefficient or permutation-AP units. The axis title calls
these method-specific raw units.

The evidence notice is shortened and reduced from **3 to 2 grid units high**.
Other card positions/sizes, score-decile and distribution settings, all queries,
all filters, other tabs and the full set of dashboard-card IDs were compared and
preserved exactly. Refinement changed only six questions' visualization settings,
the importance description and the text notice content/height. No cards were added.
Metabase's dashboard update endpoint required the unchanged tab and parameter
arrays to accompany the layout; those arrays were verified identical afterward.

The formatting/axis keys were checked against official version-tagged source:
[Scalar](https://github.com/metabase/metabase/blob/v0.58.33.1/frontend/src/metabase/visualizations/visualizations/Scalar/Scalar.tsx),
[column formatting](https://github.com/metabase/metabase/blob/v0.58.33.1/frontend/src/metabase/visualizations/lib/settings/column.js)
and [graph axes](https://github.com/metabase/metabase/blob/v0.58.33.1/frontend/src/metabase/visualizations/lib/settings/graph.js).
The browser-access host remains unavailable; rendered appearance cannot be claimed
as visually inspected. Live API queries and persisted visualization configuration
are verified. Snapshots are ignored under `data/processed/metabase-ml/refinement/`.
