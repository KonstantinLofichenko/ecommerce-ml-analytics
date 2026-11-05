# V4.1 — Initial chronological repeat-purchase experiment

Executed 30 October 2026. **LightGBM selected using validation Average Precision.** This is an initial offline experiment, not a deployment or causal inference result.

## Data and maturity policy

Read-only source: `synerise_analytics.ml_customer_features`. Validated **547,914 unique customers and 74,781 positives**, with no missing/invalid predictors, negative counts or inconsistent activity flags. Only the seven allowlisted behavioral columns are predictors. IDs, dates, cohort metadata and target never enter fitting. No source/dbt/Metabase writes.

Target: another purchase on a later represented calendar date, at most 30 dates after the first observed purchase. A negative label is available at midnight of first-date +31; the exact maturity boundary is inclusive. This preserves the date target, not 720 hours.

| Split (inclusive dates) | Customers | Positive | Negative | Prevalence | Latest label availability |
| --- | --- | --- | --- | --- | --- |
| Train: July 23–August 15 | 122,467 | 16,361 | 106,106 | 13.3595% | 2022-09-15 |
| Validation: September 15–30 | 78,700 | 11,287 | 67,413 | 14.3418% | 2022-10-31 |
| Test: November 1–7 | 33,020 | 4,440 | 28,580 | 13.4464% | 2022-12-08 |

Simulated training: September 15 midnight; model selection: October 31 midnight; test outcomes evaluated as of December 8 midnight, all under the UTC parsing convention. Training and validation outcomes are mature before their respective decision dates. Runtime guards reject unavailable outcomes; no positive-label exception shortens the embargo.

**313,727 customers excluded** in the August 16–September 14 and October 1–31 temporal gaps. They are neither training nor evaluation observations. The initial proposed October boundaries overlapped unavailable outcomes and were replaced with the approved split.

## Frozen model specification

DummyClassifier uses training prevalence (`strategy='prior'`). Logistic regression uses log1p followed by StandardScaler fitted only on training, C=1 and max_iter=2000. LightGBM uses 200 trees, learning_rate=0.05, 15 leaves, max_depth=5, min_child_samples=100, reg_lambda=1, max_bin=63, one CPU thread, deterministic/force_col_wise enabled. Seed 42. No class reweighting, resampling, early stopping or hyperparameter search. Models remain trained on the original training set; there is no validation refit.

Each threshold maximizes **validation F1**, with higher threshold breaking exact ties. F1 is an exploratory operating-point rule, not an agreed commercial cost function. Thresholds and the AP-based model choice are saved to selection.json before the first test prediction. All three frozen models are then evaluated on the holdout; test results do not select models, parameters or thresholds. Validation threshold performance is optimistic.

## Overall evaluation

### Validation

| Model | AP (primary) | ROC-AUC | Lift@10% | Brier ↓ | ECE-10 ↓ |
| --- | --- | --- | --- | --- | --- |
| dummy | 0.143418 | 0.500000 | 1.000000 | 0.122946 | 0.009823 |
| logistic | 0.216540 | 0.616676 | 1.889785 | 0.119965 | 0.005669 |
| lightgbm | 0.221153 | 0.629857 | 1.920129 | 0.119335 | 0.003436 |

| Model | Validation-selected threshold | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| dummy | 0.133595 | 0.143418 | 1.000000 | 0.250858 |
| logistic | 0.126858 | 0.192181 | 0.596704 | 0.290728 |
| lightgbm | 0.139219 | 0.204999 | 0.563923 | 0.300690 |

| Model | TN | FP | FN | TP |
| --- | --- | --- | --- | --- |
| dummy | 0 | 67413 | 0 | 11287 |
| logistic | 39103 | 28310 | 4552 | 6735 |
| lightgbm | 42729 | 24684 | 4922 | 6365 |

### Test

| Model | AP (primary) | ROC-AUC | Lift@10% | Brier ↓ | ECE-10 ↓ |
| --- | --- | --- | --- | --- | --- |
| dummy | 0.134464 | 0.500000 | 1.000000 | 0.116384 | 0.000869 |
| logistic | 0.205064 | 0.616486 | 1.925676 | 0.113733 | 0.002122 |
| lightgbm | 0.212838 | 0.626906 | 2.058559 | 0.113020 | 0.002953 |

| Model | Validation-selected threshold | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| dummy | 0.133595 | 0.134464 | 1.000000 | 0.237053 |
| logistic | 0.126858 | 0.186293 | 0.549775 | 0.278288 |
| lightgbm | 0.139219 | 0.211812 | 0.458784 | 0.289820 |

| Model | TN | FP | FN | TP |
| --- | --- | --- | --- | --- |
| dummy | 0 | 28580 | 0 | 4440 |
| logistic | 17918 | 10662 | 1999 | 2441 |
| lightgbm | 21000 | 7580 | 2403 | 2037 |

Lift uses top ceil(10% × n) scores and tie-expected positives at the cutoff; this avoids arbitrary ID ordering making the dummy baseline look useful. Dummy lift is exactly one. AP is sklearn Average Precision, not trapezoidal PR area. No confidence intervals are claimed.

## Calibration diagnostics

No post-hoc calibrator was fitted. Reliability uses ten fixed probability-width bins; ECE weights absolute bin errors by customer count. Coarse bins can hide local errors. All bins for every model/split are saved in metrics.json, alongside Brier and log loss.

| Split | Model | Mean predicted | Observed rate |
| --- | --- | --- | --- |
| validation | dummy | 0.133595 | 0.143418 |
| validation | logistic | 0.138121 | 0.143418 |
| validation | lightgbm | 0.143178 | 0.143418 |
| test | dummy | 0.133595 | 0.134464 |
| test | logistic | 0.134618 | 0.134464 |
| test | lightgbm | 0.135851 | 0.134464 |

LightGBM test reliability (nonempty bins):

| Probability bin | Customers | Mean predicted | Observed rate |
| --- | --- | --- | --- |
| [0.0, 0.1) | 3650 | 0.099092 | 0.086849 |
| [0.1, 0.2) | 25731 | 0.122617 | 0.122187 |
| [0.2, 0.3) | 2882 | 0.243762 | 0.252602 |
| [0.3, 0.4) | 663 | 0.337695 | 0.327300 |
| [0.4, 0.5) | 82 | 0.440082 | 0.365854 |
| [0.5, 0.6) | 11 | 0.541082 | 0.272727 |
| [0.6, 0.7) | 1 | 0.627564 | 1.000000 |

## Activity-group diagnostics

Groups are disjoint: at least one cart addition; other behavior including removal-only activity without additions; no recorded behavior. Each model retains its global validation-selected threshold. Group lift ranks within that group, not the global top decile.

### Validation groups

| Group | Customers | Positive | Prevalence |
| --- | --- | --- | --- |
| cart_additions | 50458 | 8450 | 16.7466% |
| other_behavior | 5972 | 772 | 12.9270% |
| no_behavior | 22270 | 2065 | 9.2726% |

| Model | Group | AP | ROC-AUC | Lift@10% | Brier | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dummy | cart_additions | 0.167466 | 0.500000 | 1.000000 | 0.140568 | 0.167466 | 1.000000 |
| dummy | other_behavior | 0.129270 | 0.500000 | 1.000000 | 0.112578 | 0.129270 | 1.000000 |
| dummy | no_behavior | 0.092726 | 0.500000 | 1.000000 | 0.085798 | 0.092726 | 1.000000 |
| logistic | cart_additions | 0.238642 | 0.605396 | 1.756143 | 0.136640 | 0.200472 | 0.724379 |
| logistic | other_behavior | 0.143483 | 0.527966 | 1.159539 | 0.112438 | 0.136082 | 0.795337 |
| logistic | no_behavior | 0.092726 | 0.500000 | 1.000000 | 0.084202 | 0.000000 | 0.000000 |
| lightgbm | cart_additions | 0.244416 | 0.626236 | 1.778628 | 0.135638 | 0.206532 | 0.739408 |
| lightgbm | other_behavior | 0.138870 | 0.505887 | 1.215988 | 0.112566 | 0.146801 | 0.151554 |
| lightgbm | no_behavior | 0.092726 | 0.500000 | 1.000000 | 0.084212 | 0.000000 | 0.000000 |

### Test groups

| Group | Customers | Positive | Prevalence |
| --- | --- | --- | --- |
| cart_additions | 18913 | 2983 | 15.7722% |
| other_behavior | 3047 | 440 | 14.4404% |
| no_behavior | 11060 | 1017 | 9.1953% |

| Model | Group | AP | ROC-AUC | Lift@10% | Brier | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dummy | cart_additions | 0.157722 | 0.500000 | 1.000000 | 0.133428 | 0.157722 | 1.000000 |
| dummy | other_behavior | 0.144404 | 0.500000 | 1.000000 | 0.123669 | 0.144404 | 1.000000 |
| dummy | no_behavior | 0.091953 | 0.500000 | 1.000000 | 0.085232 | 0.091953 | 1.000000 |
| logistic | cart_additions | 0.232715 | 0.618597 | 1.762673 | 0.129780 | 0.194938 | 0.710023 |
| logistic | other_behavior | 0.160772 | 0.528059 | 1.180656 | 0.123554 | 0.144325 | 0.734091 |
| logistic | no_behavior | 0.091953 | 0.500000 | 1.000000 | 0.083585 | 0.000000 | 0.000000 |
| lightgbm | cart_additions | 0.244246 | 0.638035 | 1.876610 | 0.128530 | 0.212944 | 0.657392 |
| lightgbm | other_behavior | 0.162256 | 0.536583 | 1.422842 | 0.123543 | 0.186275 | 0.172727 |
| lightgbm | no_behavior | 0.091953 | 0.500000 | 1.000000 | 0.083597 | 0.000000 | 0.000000 |

## Feature interpretation

| Feature | LR coefficient | LightGBM gain share | LightGBM splits |
| --- | --- | --- | --- |
| page_views_30d | 0.029443 | 39.76% | 387 |
| unique_pages_30d | 0.054566 | 31.20% | 445 |
| cart_adds_30d | 0.127686 | 10.65% | 519 |
| cart_removals_30d | 0.072412 | 7.44% | 309 |
| searches_30d | 0.137639 | 8.50% | 363 |
| has_cart_activity_30d | -0.136304 | 0.00% | 0 |
| has_behavioral_activity_30d | 0.091635 | 2.45% | 40 |

Logistic intercept: -1.909647. Coefficients refer to one training-standard-deviation change after log1p, including the binary predictors. Counts and derived flags are correlated; a negative conditional cart-flag coefficient does not mean cart additions reduce purchasing. Gain importance is training impurity reduction, not held-out permutation importance or causality. LightGBM's unused cart flag is redundant with its cart-count feature.

All no-behavior customers have identical zero feature vectors, so every model assigns one score within this group: ROC-AUC=0.5 and within-group lift=1. At the selected thresholds logistic/LightGBM predict no positives in this group. This is an information limitation, not an indication that these customers never repeat.

## Limitations and next evaluation

The test covers **seven days**, one retailer, one artifact and one temporal fold. Seasonality, weekly dependence, drift and sample uncertainty limit generalization. The 313,727-row exclusion reduces usable training history substantially. Stronger test AP for LightGBM is descriptive; no significance or production-readiness claim is made.

The source timezone and uninterrupted tracking remain **unverified**. Explicit UTC parsing fixes computation but does not establish physical UTC or resolve possible DST. History begins in the archive: first observed purchase is not first-ever acquisition. Absence of behavior can mean absence of tracking. The date target is not order count. No synthetic Amazon display fields are predictors.

Recommend obtaining a longer continuous observation period, then preregistering several rolling forward folds with labels mature before fitting/model selection, longer final holdout coverage and temporal uncertainty estimates. Keep a fresh final holdout for any future tuning now that these November results are known. This follow-up is **not implemented**.

## Reproduction and artifacts

Install the pinned runtime (Python 3.11.16 used). On macOS the LightGBM wheel requires OpenMP; `brew install libomp` was executed successfully for this run (libomp 23.1.4).

```bash
uv pip install --python .venv/bin/python -e '.[dev,ml]' -r requirements/ml-v41.txt
.venv/bin/pytest -q tests/test_repeat_purchase.py tests/test_baseline.py
.venv/bin/python scripts/train_repeat_purchase.py \
  --output data/processed/phase-4.1/NEW_RUN_DIRECTORY
```

The CLI uses the project's local .env HTTP credentials, never credential URLs. Only the existing feature table is read; the full raw-event dataset is not loaded into Python. A fresh output directory is mandatory to preserve previous runs. Reproduction reruns a frozen protocol, not another opportunity to tune against the known test.

Executed output: `data/processed/phase-4.1/initial-2026-10-30`. It contains `selection.json`, `metrics.json`, and three joblib models including logistic preprocessing. The directory is Git-ignored; no customer-level exports or prediction tables are saved. Joblib artifacts should be loaded only from trusted sources in the pinned environment.

Dataset stream SHA-256: `81fa12ff1b4c73078a9d321a6f60635dae99b13f5d5c1a54e34bfdc6746a3e62`. Elapsed load/fit/evaluation/artifact runtime: **3.16 seconds** on this machine, excluding package installation and tests. This is not a benchmark.

| Dependency | Executed version |
| --- | --- |
| numpy | 2.4.6 |
| pandas | 3.0.6 |
| scikit-learn | 1.9.1 |
| lightgbm | 4.6.0 |
| scipy | 1.17.1 |
| joblib | 1.6.0 |
| threadpoolctl | 3.7.0 |

Python: 3.11.16; platform: `macOS-27.0.1-arm64-arm-64bit`. Exact runtime versions are recorded in `requirements/ml-v41.txt`; platform/native libraries can affect bit-level results despite fixed seeds.

## Final checks for this execution

- Python suite: **87 passed, 3 skipped** in 5.62 seconds. The skipped live
  ClickHouse migration integration tests require explicit opt-in; they are not
  training-validation failures. All new V4.1 tests executed, including a guard
  proving selection.json exists before holdout prediction, calendar maturity,
  exact split boundaries, excluded gaps, invalid inputs, training-only scaling,
  feature allowlists, threshold choice and tied ranking.
- Ruff lint and formatting checks passed for all 111 Python files.
- The actual ClickHouse load and three-model experiment ran successfully; the
  skipped integration tests do not substitute for that executed experiment.
- No dbt models, source tables, Metabase cards or prediction tables were changed.
  Existing uncommitted V4 preparation files remain separate working-tree changes.
- No commits or pushes were made. Models and raw aggregate run outputs remain
  ignored; the report, code, tests and dependency pins are reviewable source files.
