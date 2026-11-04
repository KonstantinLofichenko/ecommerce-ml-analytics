# V4.1 — Preserved interactive notebook baseline

Reviewed **4 November 2026**. Evidence:
[`notebooks/01_repeat_purchase_exploration.ipynb`](../notebooks/01_repeat_purchase_exploration.ipynb).
All results below are **verified against saved notebook outputs**, not independently
reproduced by rerunning training or test evaluation. The notebook is preserved
byte-for-byte, including all outputs. No new experiment was performed.

This differs from the [earlier scripted V4.1 run](reports/phase-4.1-repeat-purchase.md).
The script uses log1p preprocessing and a different LightGBM configuration; its
metrics, selected thresholds and artifact models must not be substituted for this
notebook's results. Both records remain intact.

## Dataset, target and chronology

Source: **`synerise_analytics.ml_customer_features`**. Saved full-load output:
**547,914 rows, 11 columns**, 74,781 positives and 473,133 negatives (13.6483%
positive). Data is loaded using `SELECT * ... ORDER BY first_purchase_ts, client_id`.
Only seven explicit behavioral features enter X; y is `target_30d`. IDs, timestamps
and cohort metadata are excluded from fitting.

The target is a purchase on a **distinct later source-calendar date**, with a gap
of 1–30 calendar days inclusive after the first observed purchase. It is neither
an order count nor an exact 720-hour window. The underlying source timezone and
continuous tracking completeness remain unverified; UTC parsing in dbt is a
computational convention. First observed purchase need not be first-ever purchase.
See [feature definitions and assumptions](customer-features-v4.md).

| Partition | First-purchase dates, inclusive | Saved customer count | Saved positive rate |
| --- | --- | ---: | ---: |
| Train | 2022-07-23–2022-08-15 | 122,467 | 13.36% |
| Validation | 2022-09-15–2022-09-30 | 78,700 | 14.34% |
| Test | 2022-11-01–2022-11-07 | 33,020 | 13.45% |

The notebook's masks are half-open at August 16, October 1 and November 8.
The training mask starts at July 23 midnight; the existing table supplies the
stricter established eligibility start, July 23 00:12:25. This shortcut relies on
the unchanged source table and is not a separately enforced eligibility check.

**313,727 customers** are excluded by the August 16–September 14 and October 1–31
gaps (arithmetic from the saved partition sizes). A negative label is mature at
midnight of first-purchase date +31, because day +30 is included. Latest train
outcomes are available September 15, validation outcomes October 31 and test
outcomes December 8. Thus the approved simulated fit date September 15 and selection
date October 31 precede the next evaluation period without unavailable outcomes.
This is a static review of the dates, not a maturity assertion executed by the
notebook: it does not implement those guards itself.

The seven-day test is one short temporal slice. It cannot establish broad seasonal
or cross-retailer generalization, stability across time, or statistical significance.
Do not infer that slightly stronger validation than training metrics prove absence
of overfitting; class prevalence and temporal populations differ.

## Actual saved model configuration

The code cells explicitly specify:

```python
# Seven raw features; no log1p transform in this notebook.
model = make_pipeline(
    StandardScaler(),
    LogisticRegression(max_iter=1000, random_state=42)
)
model.fit(X_train, y_train)

lgbm_model = LGBMClassifier(
    n_estimators=100,
    learning_rate=0.05,
    max_depth=4,
    random_state=42,
    verbosity=-1
)
lgbm_model.fit(X_train, y_train)
```

The six-feature `reduced_model` uses the **same five explicit LightGBM arguments**,
excluding only `has_cart_activity_30d` from its training/validation columns. All
seven features remain in dbt and the full model. There is no class reweighting,
resampling, early stopping, calibration fit or hyperparameter search in the saved
code. Parameters not specified above are library defaults; the notebook does not
save complete `get_params()` output or full execution-time versions. We cannot
assert additional historical parameter values from today's defaults. Neither
LightGBM thread count nor deterministic/force-column settings are explicitly set.

The notebook compares against validation prevalence for baseline AP and against
constant **training prevalence** for validation/test Brier. It does not fit a
DummyClassifier or select a classification threshold. No notebook precision/recall,
F1 or confusion-matrix results should be imported from the separate scripted run.

## Saved evaluation results

| Model / partition | Average Precision | ROC-AUC | Lift@10% | Brier |
| --- | ---: | ---: | ---: | ---: |
| Logistic Regression / validation | 0.2087 | 0.6054 | 1.83× | 0.1211 |
| LightGBM / validation | 0.2209 | 0.6278 | 1.93× | 0.1194 |
| LightGBM / test | 0.2134 | 0.6238 | 2.08× | 0.1130 |

Test customer count **33,020**, positive prevalence **13.45%**. Test baseline Brier
**0.1164**; saved relative Brier improvement **2.87%**, computed in the notebook as
`1 - test_brier / test_baseline_brier` using unrounded values. Recalculating from
the four-decimal printed Brier scores will not reproduce the exact improvement.
Validation baseline AP is 0.1434 and baseline Brier is 0.1229.

AP is sklearn Average Precision, not trapezoidal PR area. Lift uses Pandas
`nlargest(n=int(len(results)*0.10), columns='probability')`, then top-decile target
rate divided by partition prevalence. This uses floor K and the Pandas default
first-occurrence tie policy; it is not the scripted run's tie-expected lift.
Sorted input row order can therefore matter at a tied cutoff. Both saved evaluation
sizes are divisible by ten, so floor versus ceil does not change K in these results.

Calibration analysis uses `calibration_curve(..., n_bins=10, strategy='quantile')`
on validation, with an embedded reliability plot and Brier scores. No post-hoc
calibrator was fitted. We inspected the code and saved metrics; numerical bin
coordinates are not separately printed, so none are fabricated here. The scripted
run's equal-width bins and ECE are separate results.

## Importance and ablation evidence

Permutation importance was computed on **validation** using Average Precision,
`n_repeats=5`, `random_state=42`, `n_jobs=-1`:

| Feature | Mean validation AP deterioration | Saved standard deviation |
| --- | ---: | ---: |
| `unique_pages_30d` | 0.054013 | 0.000746 |
| `page_views_30d` | 0.022795 | 0.000593 |
| `searches_30d` | 0.018373 | 0.000752 |
| `cart_removals_30d` | 0.010550 | 0.000245 |
| `cart_adds_30d` | 0.008695 | 0.000606 |
| `has_behavioral_activity_30d` | 0.006381 | 0.000120 |
| `has_cart_activity_30d` | 0.000000 | 0.000000 |

This measures deterioration after shuffling one feature under this fitted model;
it does **not** measure causal influence. Correlated counts/indicators can share
or mask importance. The standard deviations describe five permutations, not a
confidence interval for temporal generalization.

The saved `feature_importances_` output is: page views 331, unique pages 327,
searches 212, cart additions 204, cart removals 161, any behavior 34, cart flag 0.
This is the model's built-in importance output (default split-count semantics in
the reviewed LightGBM environment), not the permutation AP reductions above.

The six-feature ablation reports the same validation AP **0.2209** and ROC-AUC
**0.6278**. Maximum and mean absolute prediction differences both print
**0.0000000000** at ten decimal places. This supports equality at the checked
precision, not proven bitwise equality or irrelevance in future data. The final
test cell calls the original seven-feature `lgbm_model`, not `reduced_model`.
No feature was removed from the dbt table.

## Reproducibility review and limitations

- **Workflow reviewed:** the four-row teaching example, connection preview, full
  data load, X/y allowlist, chronological masks, training-only scaling, logistic
  and LightGBM fits, ranking metrics, built-in/permutation importance, ablation,
  page-count analysis, calibration and final holdout evaluation.
- **Holdout exposure:** the full-population `analysis = df.copy()` page-count/target
  summary (cell 32, one-based) includes test-period labels before the final test
  evaluation (cell 41). A training-only version follows. Saved code shows no later
  model refit after this summary, but the description “untouched test data” is not
  independently established. Treat this as exploratory baseline evidence, not a
  strictly sealed prospective holdout. Future tuning needs a fresh holdout.
- **Execution state:** 43 cells, 42 nonempty code cells and two embedded PNG figures;
  no saved error outputs. Execution counts increase from 3 to 45 with 38 absent.
  This suggests interactive history, not evidence of a fresh-kernel Run All; deleted
  or unsaved earlier actions cannot be reconstructed from the saved notebook.
- **Environment:** notebook metadata records Python **3.11.16**, and an executed
  cell prints Matplotlib **3.11.2**. Historical scikit-learn/LightGBM/NumPy versions,
  data checksum, model binaries and full model parameters were not saved in it.
  The current lock is useful for future reproduction but cannot fill that gap.
- **Current review environment, not historical proof:** clickhouse-connect 0.15.1,
  LightGBM 4.6.0, scikit-learn 1.9.1, pandas 3.1.0, NumPy 2.4.6, JupyterLab 4.6.5,
  ipykernel 7.4.0, Matplotlib 3.11.2. `uv.lock` instead pins NumPy 2.5.4;
  `uv lock --check --offline` passed. No environment synchronization was performed.
- **Coverage/quality:** the notebook prints population and split counts but lacks
  full assertions for uniqueness, finite/nonnegative features, target maturity or
  source coverage. Prior dbt/research validation is documented separately; it was
  not rerun during this review. `SELECT *` also relies on the current table schema,
  though the explicit feature allowlist protects predictor selection.
- **Access:** the connection uses interactive `getpass`, not a hardcoded password
  or automatic `.env` loading. Fixed localhost/18123/account values may need local
  configuration if deployed elsewhere. No credentials or grants were changed.
- **Preservation:** notebook SHA-256 before/after this task:
  `56c1ddbde7b35b8e858adaf2718d4bdc0ec288e988e073819bd17b0c0aa06378`.
  Structure validated with nbformat; all supplied metrics/importance values were
  found in saved outputs. This is evidence inspection, **not independent reproduction**.

Follow [notebook setup and fresh-kernel instructions](../notebooks/README.md).
No notebook cleanup was necessary for this documentation-only task. Future
quality assertions, environment capture or removal of test-exposing EDA would be
separately reviewed changes, not silent revisions of completed evidence.

Generated artifacts belong under ignored `data/processed/phase-4.1/` or `scratch/`.
Environment files, kernels' virtual environments, notebook checkpoints, model
pickles and large datasets are ignored; `.env.example` is intentionally retained.
The notebook's small saved customer previews and existing figures were preserved.
No currently configured secret values were found in its contents, and no embedded
credential URLs were found in the current lock. These checks do not guarantee the
absence of every possible secret. No training, final-test rerun, dbt/data/dashboard
change, commit or push was performed.
