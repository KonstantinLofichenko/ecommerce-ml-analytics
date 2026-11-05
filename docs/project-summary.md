# E-commerce ML Analytics — portfolio summary

Built a local **ClickHouse → dbt → Python ML → evaluation** workflow alongside
Metabase analytics, using anonymized Synerise customer behavior. The project
preserves the original REES46/DuckDB analytics work as an independent reference.

## Completed work

- Ingested 225,224,262 behavioral events and 1,534,050 product-property rows into
  native ClickHouse tables; raw duplicate rows remain intact. The final Synerise
  load used documented count-only acceptance, not full value reconciliation.
- Built customer/category/SKU funnels, time-to-conversion, cart non-conversion and
  purchase-retention reporting for the existing four-tab Metabase dashboard.
- Added deterministic Amazon-derived display labels without claiming real product
  matches or using those synthetic values as ML predictors.
- Engineered seven pre-first-purchase behavioral features for 547,914 customers,
  preserving 173,314 customers with no recorded behavior and 74,781 positive labels.
- Evaluated constant, logistic and LightGBM baselines with chronological splits,
  calendar-date label-maturity gaps, training-only preprocessing, calibration and
  ranking diagnostics; preserved a separate interactive notebook experiment.

## Results and interpretation

| LightGBM evidence | Test AP | Test ROC-AUC | Lift@10% | Brier |
| --- | ---: | ---: | ---: | ---: |
| Preserved notebook outputs | 0.2134 | 0.6238 | 2.08× | 0.1130 |
| Executed scripted run | 0.2128 | 0.6269 | 2.06× | 0.1130 |

The test has 33,020 customers and 13.45% positive prevalence. Models improve ranking
relative to a constant baseline, with modest discrimination. Lift is predictive
prioritization, not measured incremental sales or causal impact. The notebook uses
100-tree/depth-4 LightGBM; the script uses 200-tree/depth-5 LightGBM and different
logistic preprocessing. These are separate results, not exact reruns of one model.

## Engineering evidence and limits

The repository contains dbt key/grain/chronology tests, synthetic Python boundary
and leakage checks, runtime pins, an approved-split maturity policy, source/data
checksums where available and provenance-labeled analytical SQL. Secrets, raw data,
model binaries and generated outputs remain outside Git. The original notebook
and both result records are preserved unchanged.

The target is a later distinct source-calendar purchase date within 30 days of
first observed purchase, not an order or 720-hour outcome. The first-purchase split
uses 122,467 train, 78,700 validation and 33,020 test customers, with 313,727 in
excluded maturity gaps. One seven-day test fold limits temporal generalization.
Source timezone and continuous tracking are unverified, and first observed is not
necessarily first-ever purchase. Full-population notebook EDA includes test-period
labels, so that notebook is exploratory baseline evidence rather than a sealed
prospective holdout. Its complete execution-time environment was not captured.

Completed scope is offline analytics and baseline modeling. A longer dataset,
fresh holdout, rolling chronological validation, serving and Airflow DAGs are
potential future work, **not claims of implemented functionality**.

[Architecture](architecture.md) · [Reproduction](project-reproduction.md) ·
[Notebook report](ml_baseline_v4_1.md) · [Scripted report](reports/phase-4.1-repeat-purchase.md) ·
[Final audit](reports/project-finalization.md)
