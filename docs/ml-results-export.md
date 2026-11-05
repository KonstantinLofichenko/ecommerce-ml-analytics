# Frozen ML results reporting export

Implemented, dry-run validated and **published 5 November 2026**, following explicit
user approval. Only the six new ML reporting objects in `synerise_analytics` were
created. No grants or dashboards were changed. The exporter never fits models or
calls the historical evaluation routine.

## Evidence and scope

The entry point is [`scripts/export_ml_results.py`](../scripts/export_ml_results.py).
Preparation and publication are separate modules under
[`src/ecommerce_analytics/reporting/`](../src/ecommerce_analytics/reporting/).

| Experiment ID | Available evidence | Export scope |
| --- | --- | --- |
| `v4.1-scripted-2026-10-30` | Three trusted joblib artifacts, `metrics.json`, `selection.json` | Validation/test inference, saved overall metrics, saved importance, saved calibration |
| `v4.1-notebook-preserved` | SHA-pinned original notebook and its saved outputs | Rounded historical summary metrics and importance only |

Scripted inputs live under ignored
`data/processed/phase-4.1/initial-2026-10-30/`. There are no saved original individual
predictions. New scores are explicitly `provenance='artifact_inference'`, never
represented as original historical scores. `model_version` is the artifact SHA-256.

Notebook records carry `historical_notebook_saved_output` and a notebook SHA-based
version. Its model artifacts and numerical calibration coordinates are unavailable;
no notebook predictions/calibration are invented. Historical evaluation timestamps
were not recorded precisely: `evaluated_at` is NULL. Notebook values are transcribed
from verified, hash-pinned outputs and labeled `reported_rounded`. They are not
independently reproduced. The original notebook remains unchanged.

The scripted logistic model uses log1p then training-fitted StandardScaler and
LogisticRegression (`C=1`, `max_iter=2000`, seed 42); LightGBM has 200 trees,
learning rate .05, 15 leaves, depth 5, minimum child samples 100, lambda 1,
max_bin 63, one thread and deterministic column-wise fitting. The notebook instead
uses raw-feature scaling, logistic max_iter 1000, and LightGBM 100 trees/depth 4.
See the separate [scripted report](reports/phase-4.1-repeat-purchase.md) and
[notebook report](ml_baseline_v4_1.md). Their scores must not be mixed.

## Executed dry-run results

All three artifacts loaded successfully using Python **3.11.16**, matching the
historical Python version. Exact recorded packages matched: NumPy 2.4.6, pandas
3.0.6, scikit-learn 1.9.1, LightGBM 4.6.0, SciPy 1.17.1, joblib 1.6.0,
threadpoolctl 3.7.0. Model feature names/order, two classes, model configurations,
scaler training sample count and dummy prior passed compatibility checks.

The default `.venv` was deliberately checked and rejected **before artifact loading**:
pandas 3.1.0 differs from recorded 3.0.6. No dependency changes were made. The
successful run used the existing pinned reproduction environment at
`/tmp/ecommerce-portfolio-repro`; its location is local, not a project requirement.

Source: `synerise_analytics.ml_customer_features`, **547,914 unique customers**,
**74,781 positives**. The exact ordered TSV SHA-256 matched historical metadata:
`81fa12ff1b4c73078a9d321a6f60635dae99b13f5d5c1a54e34bfdc6746a3e62`.
No dataset mismatch was found. Features, finite/nonnegative counts and binary
indicator consistency use the existing dataset validator. Chronological split and
calendar-date maturity checks reuse the existing validated implementation.

| Split | Customers | Positive customers | Prediction rows (three models) |
| --- | ---: | ---: | ---: |
| Train, compatibility check only | 122,467 | 16,361 | 0 |
| Validation, September 15–30 | 78,700 | 11,287 | 236,100 |
| Test, November 1–7 | 33,020 | 4,440 | 99,060 |
| Total scored | 111,720 | 15,727 | 335,160 |

There are **313,727 excluded customers** in the maturity gaps, with no exported
scores. Every model has the same validation/test customer IDs and targets, taken
from the same frozen split frames. Prepared records are checked for unique keys,
valid probabilities, targets, identity, provenance, counts and checksums.

| Record kind | Scripted | Notebook | Total |
| --- | ---: | ---: | ---: |
| Predictions | 335,160 | 0 | 335,160 |
| Metrics | 126 | 16 | 142 |
| Feature importance | 21 | 14 | 35 |
| Calibration bins | 60 | 0 | 60 |

The local package contains **335,397 reporting records**. Its canonical-line SHA-256:
`13e603fa5c7c1221a522ff78259d2a3fa968404c81c16a70fc5fc080444b91b4`.
Export ID: `c498f2518f8708db6ee32c0802b36619a3a44b1b39ba325b4fe5b572422333e7`.
Actual package: ignored `data/processed/ml-reporting/validated-2026-11-05/`, containing
`rows.jsonl.gz` and `package.json` (identities, versions, hashes, exact counts,
positive counts, split policy and scoring time).

Inference mean probabilities and all 60 saved bin counts, mean probabilities and
observed rates agree with historical scripted summaries (floating means compared
at rtol 1e-12 / atol 1e-14). Original numeric performance metrics are copied unchanged;
AP/AUC/lift, thresholds and final-test evaluation were **not recomputed or selected**.
Empty calibration bins retain NULL means. Saved subgroup analyses remain in the
original metrics artifact/report; these reporting views expose overall metrics.

## Published ClickHouse objects

Destination is the existing `synerise_analytics` database. DDL is defined in
[`publication.py`](../src/ecommerce_analytics/reporting/publication.py), not dbt.
Two ordinary MergeTree backing tables provide one manifest-gated release across
four typed reporting views:

| Object | Grain and columns |
| --- | --- |
| `_ml_export_rows` | Export/attempt/record; `export_id String`, `attempt_id String`, `record_type LowCardinality(String)`, `payload String` (canonical JSON) |
| `_ml_export_publications` | One committed export; IDs, `bundle_digest String`, `metadata String`, `published_at DateTime64(6,'UTC')` |
| `ml_customer_predictions` | Experiment/model/version/split/customer; `client_id Int64`, `prediction_probability Float64`, `actual_target Int64`, `first_purchase_ts String`, `scored_at String` |
| `ml_experiment_metrics` | Experiment/model/version/split/metric; metric name, Float64 value, precision label, `evaluated_at Nullable(String)` |
| `ml_feature_importance` | Experiment/model/version/split/feature/method; Float64 importance |
| `ml_calibration` | Experiment/model/version/split/bin; Float64 boundaries, Int64 count, Nullable(Float64) predicted/observed means |

All views also expose export/attempt IDs and String experiment/model/version/split/
provenance fields. Prediction timestamps are ISO strings with the **computational
UTC convention**, avoiding a claim of verified source timezone. `scored_at` is the
actual inference time from the committed package metadata, not the historical
training/evaluation date. Signed original client IDs remain signed.

Saved scripted metric rows include AP, ROC-AUC, Brier, prevalence, population,
confusion matrix components, threshold precision/recall/F1, lift and calibration
error. Importance methods remain separate: standardized-log1p logistic coefficients,
LightGBM gain/split counts, and notebook validation permutation AP deterioration.
Permutation importance is not causal influence.

## Idempotency, recovery and limits

Preparation validates dependencies **before unpickling**, then verifies dataset
checksum and split maturity. Only trusted local artifacts may be supplied: joblib
can execute code, and local hashes are integrity identifiers, not signatures.

An immutable export ID hashes the policy, dataset, all three artifacts, saved
metrics/selection and notebook. Row bytes are deterministic: scoring time is kept
in manifest metadata, outside the row digest. Reusing a complete package validates
its checksums without scoring again. Incomplete local packages have no valid
manifest and cannot publish; preserve them as evidence and use a fresh output path.

Publication uses a single-host advisory writer lock and a fresh attempt UUID. It
preflights managed object ownership/DDL before creating missing objects; it never
replaces existing analytics tables. Batches of 5,000 rows insert synchronously into
the backing store, with no automatic INSERT retries. Exact counts and independent
MD5/SHA-256-derived UInt256 multiset sums are checked against locally validated
rows. These checks preserve multiplicity but are probabilistic integrity evidence.

Only after verification does one manifest INSERT make all four views readable.
A lost row-insert response leaves an unpublished attempt; rerunning starts fresh.
A lost manifest response is resolved by SELECT, never a blind repeated INSERT.
An existing identical committed bundle is revalidated and returns `validated_noop`;
a conflicting bundle under the same identity is refused. Existing exports are
immutable. No deletion/cleanup is automatic. Unpublished rows may remain after a
failure and need separately reviewed, exact-attempt cleanup later.

No cross-table transaction is assumed. Multi-host or out-of-band writers are
unsupported; the local lock cannot coordinate them. Backing tables should be
operator-only, with BI granted SELECT on consumer views after review. This task
changes no grants. An administrator can always inspect unpublished backing rows.

## Reproduction and operation

Run from repository root with the existing pinned ML dependencies. If a dedicated
environment is needed, these are **setup commands**, not changes performed here:

```bash
uv venv --python 3.11 scratch/ml-export-env
uv pip install --python scratch/ml-export-env/bin/python \
  --constraint requirements/ml-v41.txt -e '.[dev,ml]'

# Default mode is dry-run: only SELECTs against production ClickHouse.
scratch/ml-export-env/bin/python scripts/export_ml_results.py \
  --output data/processed/ml-reporting/reviewed-export

# Explicit integration opt-in: synthetic fixtures in UUID-owned test databases only.
ECOMMERCE_ML_REPORTING_TESTS=1 scratch/ml-export-env/bin/python -m pytest \
  tests/test_ml_reporting.py tests/test_repeat_purchase.py tests/test_baseline.py -q
```

The source SELECT reuses existing `load_dataset()` connection conventions. The
existing `.env` reader supports `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`,
`CLICKHOUSE_HTTP_PORT`, optional `CLICKHOUSE_MIGRATION_URL`; shell exports override
file values. Credentials are never arguments, URLs, payloads or committed files.
Use the existing local operator account; a future production writer needs explicit
CREATE/INSERT/SELECT access for the destination objects. No credentials are added.

The approved publication command, executed twice in the verified pinned environment:

```bash
/tmp/ecommerce-portfolio-repro/bin/python scripts/export_ml_results.py \
  --output data/processed/ml-reporting/validated-2026-11-05 \
  --database synerise_analytics --publish
```

The first invocation returned `published`; the second returned `validated_noop`.
The destination database must already exist.
The CLI verifies artifacts and the live dataset again, then reuses the validated
package. To rerun safely, retain the package; do not manually append reporting rows.
Artifacts/packages stay under ignored data directories, never Git.

Metabase can query the consumer views using an account authorized to read them,
filtering explicitly by `experiment_id`, `model_name`, `model_version`,
`dataset_split` and metric/method. Always display provenance. Do not join notebook
summaries to scripted customer scores or sum metrics across models/experiments.
For example (read-only query):

```sql
SELECT model_name, dataset_split, metric_name, metric_value, provenance
FROM synerise_analytics.ml_experiment_metrics
WHERE experiment_id = 'v4.1-scripted-2026-10-30'
  AND metric_name IN ('average_precision', 'roc_auc', 'lift_10pct', 'brier_score')
ORDER BY dataset_split, model_name, metric_name;
```

## Validation and remaining risks

**45 tests passed**, including **7 live isolated ClickHouse integration cases**
(success/no-op, lost row acknowledgement, lost publication acknowledgement,
same-count corruption, unmanaged collision, managed DDL tampering, conflicting
bundle) plus existing ML unit tests. Test databases were UUID-owned, checked before
removal, and none remained. All four reporting views were exercised, including
empty-bin NULLs and signed identifiers. Ruff lint/format and diff checks passed.

Protected notebook, dbt SQL/YAML, model-training modules, original joblib artifacts,
selection/metrics JSON and historical reports retained their SHA-256 values.
The initial dry-run left production reporting objects absent; the subsequently
approved publication created only the six managed objects listed above. Read-only
checks confirmed REES46
**20,692,840 rows** and feature population **547,914 / 74,781 positives**.
Existing Airflow-removal work and the unrelated PDF remain outside this task.
No retraining, source/dashboard change, commit or push occurred.

Remaining limitations: exact historical dependencies and locally held artifacts are
required; original notebook artifacts are missing; its held-out labels were exposed
in exploratory EDA; test coverage spans only seven days; source timezone and
continuous collection are unverified. Inference reproduces frozen-model scores,
not an independent validation of original training. These limitations are retained,
not repaired by reporting export. Production publication and its no-op rerun both
completed successfully. View access was verified with the configured operator
account; restricted BI grants and dashboard integration were not changed.


## Final publication checkpoint — 5 November 2026

Published at **2026-11-05 17:59:04.206494 UTC**, using the existing validated local
package. Preparation rechecked the exact historical dependencies, live dataset
checksum and artifact compatibility, then reused the package without scoring or
retraining models. Both publication invocations used
`/tmp/ecommerce-portfolio-repro/bin/python`.

- Export ID: `c498f2518f8708db6ee32c0802b36619a3a44b1b39ba325b4fe5b572422333e7`.
- Attempt ID: `004af5d343a54de9af100e9fa6f233ab`.
- First invocation: `published`; second invocation: `validated_noop`, same attempt.
- Both server-side multiset checksums and exact record counts passed.
- Backing storage remains **335,397 rows and one publication manifest** after
  rerunning; no duplicate or additional attempt rows were created.

| Accessible reporting view in `synerise_analytics` | Published rows |
| --- | ---: |
| `ml_customer_predictions` | 335,160 |
| `ml_experiment_metrics` | 142 |
| `ml_feature_importance` | 35 |
| `ml_calibration` | 60 |

All **335,160 prediction keys are unique**, covering **111,720 customers**. There
are zero invalid probabilities or binary targets. Each of three models has
78,700 validation customers / 11,287 positives and 33,020 test customers / 4,440
positives. All predictions identify `v4.1-scripted-2026-10-30` and
`artifact_inference`. No training/gap/notebook predictions were published.

The separate `v4.1-notebook-preserved` identity has 16 metrics and 14 importance
records with `historical_notebook_saved_output`. Scripted summaries have 126
metrics, 21 importance records and 60 calibration bins, labeled
`original_scripted_metrics_json`. Historical values were not recalculated.

Before/after checks, repeated after the no-op run, matched **49 existing database
objects** (UUID, engine and DDL), **41 existing physical-table row counts**, and
SHA-256 hashes of **66 protected files**: the historical notebook, original model
artifacts/metrics/selection, training modules, dbt models/macros and historical
ML reports. Exactly the six documented reporting objects were added. REES46
remains **20,692,840 rows**; the feature table remains **547,914 rows / 74,781
positives**. Row-count/identity checks are not full content hashes of every existing
analytics table; the publisher issues no writes against those tables.

Local publication logs and aggregate preservation evidence are under ignored
`data/processed/ml-reporting/publication-2026-11-05/`. No model, notebook, dbt or
exporter code changes were necessary for publication. No credentials, grants,
source datasets, Metabase configuration, commits or pushes were changed.
There were no publication errors or unresolved reconciliation discrepancies.

Representative read-only verification queries:

```sql
SELECT 'predictions' AS record_type, count() AS records
  FROM synerise_analytics.ml_customer_predictions
UNION ALL
SELECT 'metrics', count()
  FROM synerise_analytics.ml_experiment_metrics
UNION ALL
SELECT 'importance', count()
  FROM synerise_analytics.ml_feature_importance
UNION ALL
SELECT 'calibration', count()
  FROM synerise_analytics.ml_calibration;

SELECT experiment_id, model_name, dataset_split, provenance,
       count() AS predictions, sum(actual_target) AS positives
  FROM synerise_analytics.ml_customer_predictions
 GROUP BY experiment_id, model_name, dataset_split, provenance
 ORDER BY dataset_split, model_name;

SELECT experiment_id, provenance, count() AS metrics
  FROM synerise_analytics.ml_experiment_metrics
 GROUP BY experiment_id, provenance;

SELECT count() AS predictions,
       uniqExact(tuple(experiment_id, model_name, model_version,
                       dataset_split, client_id)) AS unique_prediction_keys,
       uniqExact(client_id) AS customers
  FROM synerise_analytics.ml_customer_predictions;

-- Operator-only manifest inspection; no credentials or model binaries are stored here.
SELECT export_id, attempt_id, bundle_digest, published_at
  FROM synerise_analytics._ml_export_publications;
```
