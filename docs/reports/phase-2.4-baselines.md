# Phase 2.4 — Chronological validation and baseline modeling

## Protocol and scope

DuckDB remains the validated reference database and is opened read-only. ClickHouse is the target analytical storage for a later phase; no migration is implemented here. Only the compact customer feature table is loaded into Pandas, not raw events. The existing event-based target is unchanged: any purchase in [t, t+14 days), including purchases in a session already purchasing before the snapshot.

This is a **provisional baseline**, not a final reliable estimate of deployment performance. There are only two training dates and one validation/test date each. A February result cannot establish robustness to seasonality or later cohorts.

## Dataset inspection

### Feature schema

| column_name | column_type | null | key | default | extra |
| --- | --- | --- | --- | --- | --- |
| prediction_date | DATE | NO | PRI | — | — |
| user_id | VARCHAR | NO | PRI | — | — |
| target_14d | TINYINT | NO | — | — | — |
| days_since_last_purchase | DOUBLE | NO | — | — | — |
| purchase_sessions_30d | BIGINT | NO | — | — | — |
| sessions_30d | BIGINT | NO | — | — | — |
| view_events_30d | BIGINT | NO | — | — | — |
| cart_events_30d | BIGINT | NO | — | — | — |
| remove_events_30d | BIGINT | NO | — | — | — |
| purchase_events_30d | BIGINT | NO | — | — | — |
| distinct_products_30d | BIGINT | NO | — | — | — |
| days_since_last_event | DOUBLE | NO | — | — | — |
| historical_purchasing_sessions | BIGINT | NO | — | — | — |

### Feature quality

| feature | missing | infinite | negative |
| --- | --- | --- | --- |
| days_since_last_purchase | 0 | 0 | 0 |
| purchase_sessions_30d | 0 | 0 | 0 |
| sessions_30d | 0 | 0 | 0 |
| view_events_30d | 0 | 0 | 0 |
| cart_events_30d | 0 | 0 | 0 |
| remove_events_30d | 0 | 0 | 0 |
| purchase_events_30d | 0 | 0 | 0 |
| distinct_products_30d | 0 | 0 | 0 |
| days_since_last_event | 0 | 0 | 0 |
| historical_purchasing_sessions | 0 | 0 | 0 |

### Class balance

| prediction_date | rows | positives | positive_rate |
| --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 25762 | 2456 | 0.095334 |
| 2019-12-01 00:00:00 | 52523 | 3493 | 0.066504 |
| 2020-01-01 00:00:00 | 72225 | 3831 | 0.053043 |
| 2020-02-01 00:00:00 | 92652 | 4528 | 0.048871 |

### Customer overlap

| earlier_snapshot | later_snapshot | shared_customers | earlier_customers | later_customers | later_overlap_fraction |
| --- | --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | 2019-12-01 00:00:00 | 25762 | 25762 | 52523 | 0.490490 |
| 2019-11-01 00:00:00 | 2020-01-01 00:00:00 | 25762 | 25762 | 72225 | 0.356691 |
| 2019-11-01 00:00:00 | 2020-02-01 00:00:00 | 25762 | 25762 | 92652 | 0.278051 |
| 2019-12-01 00:00:00 | 2020-01-01 00:00:00 | 52523 | 52523 | 72225 | 0.727214 |
| 2019-12-01 00:00:00 | 2020-02-01 00:00:00 | 52523 | 52523 | 92652 | 0.566885 |
| 2020-01-01 00:00:00 | 2020-02-01 00:00:00 | 72225 | 72225 | 92652 | 0.779530 |

### Feature distributions by date

| prediction_date | feature | min | p25 | median | p75 | p95 | max | mean | zero_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2019-11-01 00:00:00 | days_since_last_purchase | 0.003067 | 7.494392 | 15.144439 | 22.733160 | 29.445413 | 30.992708 | 15.110929 | 0 |
| 2019-12-01 00:00:00 | days_since_last_purchase | 0.024375 | 8.665706 | 23.305856 | 41.393698 | 57.343432 | 60.992708 | 25.824115 | 0 |
| 2020-01-01 00:00:00 | days_since_last_purchase | 0.001910 | 21.516991 | 39.465880 | 63.238970 | 86.153667 | 91.992708 | 42.828393 | 0 |
| 2020-02-01 00:00:00 | days_since_last_purchase | 0.001088 | 22.619896 | 56.719803 | 84.647694 | 115.376408 | 122.992708 | 56.241401 | 0 |
| 2019-11-01 00:00:00 | purchase_sessions_30d | 0 | 1 | 1 | 1 | 2 | 31 | 1.099177 | 0.031675 |
| 2019-12-01 00:00:00 | purchase_sessions_30d | 0 | 0 | 1 | 1 | 2 | 23 | 0.696228 | 0.399806 |
| 2020-01-01 00:00:00 | purchase_sessions_30d | 0 | 0 | 0 | 1 | 1 | 31 | 0.388619 | 0.654939 |
| 2020-02-01 00:00:00 | purchase_sessions_30d | 0 | 0 | 0 | 1 | 1 | 18 | 0.344806 | 0.699035 |
| 2019-11-01 00:00:00 | sessions_30d | 0 | 1 | 3 | 7 | 26 | 1,347 | 7.540874 | 0.019797 |
| 2019-12-01 00:00:00 | sessions_30d | 0 | 0 | 2 | 5 | 21 | 2,030 | 5.658664 | 0.295071 |
| 2020-01-01 00:00:00 | sessions_30d | 0 | 0 | 0 | 3 | 12 | 1,664 | 3.086964 | 0.506321 |
| 2020-02-01 00:00:00 | sessions_30d | 0 | 0 | 0 | 2 | 12 | 1,864 | 2.952003 | 0.571914 |
| 2019-11-01 00:00:00 | view_events_30d | 0 | 3 | 9 | 26 | 92 | 1,808 | 23.870235 | 0.082990 |
| 2019-12-01 00:00:00 | view_events_30d | 0 | 0 | 4 | 17 | 75 | 2,272 | 17.176532 | 0.335110 |
| 2020-01-01 00:00:00 | view_events_30d | 0 | 0 | 0 | 7 | 44 | 1,832 | 9.100948 | 0.538318 |
| 2020-02-01 00:00:00 | view_events_30d | 0 | 0 | 0 | 5 | 44 | 2,041 | 8.841644 | 0.597170 |
| 2019-11-01 00:00:00 | cart_events_30d | 0 | 4 | 11 | 24 | 70 | 1,047 | 20.419028 | 0.037730 |
| 2019-12-01 00:00:00 | cart_events_30d | 0 | 0 | 5 | 17 | 61 | 1,458 | 14.583935 | 0.349257 |
| 2020-01-01 00:00:00 | cart_events_30d | 0 | 0 | 0 | 7 | 34 | 1,336 | 7.064438 | 0.582264 |
| 2020-02-01 00:00:00 | cart_events_30d | 0 | 0 | 0 | 6 | 36 | 1,134 | 7.072767 | 0.635993 |
| 2019-11-01 00:00:00 | remove_events_30d | 0 | 1 | 4 | 14 | 62 | 1,861 | 15.381104 | 0.228282 |
| 2019-12-01 00:00:00 | remove_events_30d | 0 | 0 | 1 | 9 | 51 | 2,480 | 11.094225 | 0.477695 |
| 2020-01-01 00:00:00 | remove_events_30d | 0 | 0 | 0 | 2 | 27 | 2,309 | 5.458290 | 0.686120 |
| 2020-02-01 00:00:00 | remove_events_30d | 0 | 0 | 0 | 1 | 28 | 1,178 | 5.435673 | 0.719553 |
| 2019-11-01 00:00:00 | purchase_events_30d | 0 | 3 | 6 | 12 | 29 | 329 | 9.205341 | 0.031675 |
| 2019-12-01 00:00:00 | purchase_events_30d | 0 | 0 | 2 | 8 | 25 | 438 | 6.138587 | 0.399806 |
| 2020-01-01 00:00:00 | purchase_events_30d | 0 | 0 | 0 | 3 | 14 | 399 | 2.851367 | 0.654939 |
| 2020-02-01 00:00:00 | purchase_events_30d | 0 | 0 | 0 | 2 | 15 | 263 | 2.811898 | 0.699035 |
| 2019-11-01 00:00:00 | distinct_products_30d | 0 | 7 | 16 | 35 | 99 | 1,104 | 29.201537 | 0.019797 |
| 2019-12-01 00:00:00 | distinct_products_30d | 0 | 0 | 7 | 25 | 84 | 1,582 | 20.822973 | 0.295071 |
| 2020-01-01 00:00:00 | distinct_products_30d | 0 | 0 | 0 | 11 | 51 | 1,420 | 10.721925 | 0.506321 |
| 2020-02-01 00:00:00 | distinct_products_30d | 0 | 0 | 0 | 9 | 54 | 1,468 | 10.562039 | 0.571914 |
| 2019-11-01 00:00:00 | days_since_last_event | 0.000278 | 3.643102 | 10.448362 | 19.355272 | 28.480323 | 30.991088 | 12.092383 | 0 |
| 2019-12-01 00:00:00 | days_since_last_event | 0.000440 | 5.052708 | 15.261678 | 33.722112 | 54.549204 | 60.991088 | 20.457087 | 0 |
| 2020-01-01 00:00:00 | days_since_last_event | 0.000752 | 13.167373 | 30.451134 | 53.157419 | 83.183708 | 91.991088 | 34.712489 | 0 |
| 2020-02-01 00:00:00 | days_since_last_event | 0.000394 | 11.425286 | 40.620243 | 71.398012 | 110.528861 | 122.991088 | 45.142134 | 0 |
| 2019-11-01 00:00:00 | historical_purchasing_sessions | 1 | 1 | 1 | 1 | 2 | 31 | 1.138343 | 0 |
| 2019-12-01 00:00:00 | historical_purchasing_sessions | 1 | 1 | 1 | 1 | 2 | 54 | 1.250938 | 0 |
| 2020-01-01 00:00:00 | historical_purchasing_sessions | 1 | 1 | 1 | 1 | 3 | 85 | 1.306888 | 0 |
| 2020-02-01 00:00:00 | historical_purchasing_sessions | 1 | 1 | 1 | 1 | 3 | 103 | 1.365356 | 0 |

## Chronological validation

| split | rows | customers | prevalence | first_snapshot | last_snapshot | last_label_end_exclusive |
| --- | --- | --- | --- | --- | --- | --- |
| train | 78285 | 52523 | 0.075992 | 2019-11-01 00:00:00 | 2019-12-01 00:00:00 | 2019-12-15 00:00:00 |
| validation | 72225 | 72225 | 0.053043 | 2020-01-01 00:00:00 | 2020-01-01 00:00:00 | 2020-01-15 00:00:00 |
| test | 92652 | 92652 | 0.048871 | 2020-02-01 00:00:00 | 2020-02-01 00:00:00 | 2020-02-15 00:00:00 |

Training uses November 1 and December 1 only. Validation is January 1; test is February 1. Training labels end December 15, before January 1; validation labels end January 15, before February 1. The pipeline asserts strict separation of these label-window ends from subsequent evaluation dates. There is no random row split and no retraining on validation before test evaluation.

Customer overlap is expected for an expanding prior-purchaser cohort. It matches the intended known-customer use case but does not measure cold-start generalization. Repeated customers and correlated histories mean rows are not independent. IDs and prediction dates are excluded from the predictive feature allowlist. Long-lived sessions cannot leak their future flags because features were computed from pre-snapshot raw events. Source duplicates, missing-session undercounts, observed rather than lifetime history, and changing history lengths remain limitations. This task checks the feature table, not an independent reconstruction of its upstream temporal provenance; see the Phase 2.3 audit and tests.

## Frozen baseline specification

Constant: predict the pooled training positive rate for everyone. Logistic: the ten explicitly allowed historical features, log1p transform for nonnegative skewed counts/recencies, StandardScaler fitted only on training, and L2 logistic regression with C=1, lbfgs, max_iter=2000, seed=42, no class weighting. Invalid/missing/infinite features fail inspection instead of being silently dropped or imputed. Convergence warnings fail the run. These settings were fixed before any evaluation; no search or test-based threshold selection is performed.

Thresholds 0.05, 0.10, 0.20, 0.50 are diagnostic, not selected deployment cutoffs. Budget fractions 1%, 5%, 10% use K=ceil(n×fraction). Operational score ties are broken by lexical customer ID solely for deterministic output, never as an input feature. Tie-expected precision/lift average over random selection within the cutoff tie, so the constant baseline has expected lift 1.

## Validation and test metrics

Average Precision is the reported PR summary, not trapezoidal PR-AUC. Higher ROC-AUC/AP are better; lower Brier/log-loss are better. AP must be compared with the date-specific prevalence. Confusion matrices are reported as tn/fp/fn/tp. Precision is reported as zero when a threshold selects nobody, together with the selected count.

### Metrics

| split | model | rows | positives | prevalence | roc_auc | average_precision | brier_score | log_loss | mean_probability | ece_10_bins |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| validation | constant | 72225 | 3831 | 0.053043 | 0.500000 | 0.053043 | 0.050756 | 0.211540 | 0.075992 | 0.022949 |
| validation | logistic | 72225 | 3831 | 0.053043 | 0.790485 | 0.249240 | 0.044905 | 0.174233 | 0.058503 | 0.005461 |
| test | constant | 92652 | 4528 | 0.048871 | 0.500000 | 0.048871 | 0.047218 | 0.201119 | 0.075992 | 0.027121 |
| test | logistic | 92652 | 4528 | 0.048871 | 0.817659 | 0.252566 | 0.042101 | 0.162147 | 0.065718 | 0.016847 |

### Thresholds

| split | model | threshold | precision | recall | predicted_positive | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| validation | constant | 0.050000 | 0.053043 | 1 | 72225 | 0 | 68394 | 0 | 3831 |
| validation | constant | 0.100000 | 0 | 0 | 0 | 68394 | 0 | 3831 | 0 |
| validation | constant | 0.200000 | 0 | 0 | 0 | 68394 | 0 | 3831 | 0 |
| validation | constant | 0.500000 | 0 | 0 | 0 | 68394 | 0 | 3831 | 0 |
| validation | logistic | 0.050000 | 0.127875 | 0.724093 | 21693 | 49475 | 18919 | 1057 | 2774 |
| validation | logistic | 0.100000 | 0.199801 | 0.525189 | 10070 | 60336 | 8058 | 1819 | 2012 |
| validation | logistic | 0.200000 | 0.303084 | 0.312973 | 3956 | 65637 | 2757 | 2632 | 1199 |
| validation | logistic | 0.500000 | 0.523719 | 0.072044 | 527 | 68143 | 251 | 3555 | 276 |
| test | constant | 0.050000 | 0.048871 | 1 | 92652 | 0 | 88124 | 0 | 4528 |
| test | constant | 0.100000 | 0 | 0 | 0 | 88124 | 0 | 4528 | 0 |
| test | constant | 0.200000 | 0 | 0 | 0 | 88124 | 0 | 4528 | 0 |
| test | constant | 0.500000 | 0 | 0 | 0 | 88124 | 0 | 4528 | 0 |
| test | logistic | 0.050000 | 0.122837 | 0.774293 | 28542 | 63088 | 25036 | 1022 | 3506 |
| test | logistic | 0.100000 | 0.181259 | 0.611307 | 15271 | 75621 | 12503 | 1760 | 2768 |
| test | logistic | 0.200000 | 0.261463 | 0.410557 | 7110 | 82873 | 5251 | 2669 | 1859 |
| test | logistic | 0.500000 | 0.448636 | 0.123454 | 1246 | 87437 | 687 | 3969 | 559 |

### Ranking

| split | model | fraction | k | precision_at_k | lift_at_k | recall_at_k | tie_expected_precision_at_k | tie_expected_lift_at_k | cutoff_tie_customers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| validation | constant | 0.010000 | 723 | 0.100968 | 1.903531 | 0.019055 | 0.053043 | 1.000000 | 72225 |
| validation | constant | 0.050000 | 3612 | 0.088594 | 1.670235 | 0.083529 | 0.053043 | 1 | 72225 |
| validation | constant | 0.100000 | 7223 | 0.080161 | 1.511250 | 0.151135 | 0.053043 | 1 | 72225 |
| validation | logistic | 0.010000 | 723 | 0.500692 | 9.439428 | 0.094492 | 0.500692 | 9.439428 | 1 |
| validation | logistic | 0.050000 | 3612 | 0.315615 | 5.950213 | 0.297572 | 0.315615 | 5.950213 | 1 |
| validation | logistic | 0.100000 | 7223 | 0.234944 | 4.429346 | 0.442965 | 0.234944 | 4.429346 | 1 |
| test | constant | 0.010000 | 927 | 0.100324 | 2.052823 | 0.020539 | 0.048871 | 1 | 92652 |
| test | constant | 0.050000 | 4633 | 0.084179 | 1.722466 | 0.086131 | 0.048871 | 1 | 92652 |
| test | constant | 0.100000 | 9266 | 0.076732 | 1.570094 | 0.157023 | 0.048871 | 1 | 92652 |
| test | logistic | 0.010000 | 927 | 0.462783 | 9.469476 | 0.094744 | 0.462783 | 9.469476 | 1 |
| test | logistic | 0.050000 | 4633 | 0.309087 | 6.324542 | 0.316254 | 0.309087 | 6.324542 | 1 |
| test | logistic | 0.100000 | 9266 | 0.233758 | 4.783156 | 0.478357 | 0.233758 | 4.783156 | 1 |

### Calibration

| split | model | lower | upper | rows | mean_probability | observed_rate |
| --- | --- | --- | --- | --- | --- | --- |
| validation | constant | 0 | 0.100000 | 72225 | 0.075992 | 0.053043 |
| validation | constant | 0.100000 | 0.200000 | 0 | — | — |
| validation | constant | 0.200000 | 0.300000 | 0 | — | — |
| validation | constant | 0.300000 | 0.400000 | 0 | — | — |
| validation | constant | 0.400000 | 0.500000 | 0 | — | — |
| validation | constant | 0.500000 | 0.600000 | 0 | — | — |
| validation | constant | 0.600000 | 0.700000 | 0 | — | — |
| validation | constant | 0.700000 | 0.800000 | 0 | — | — |
| validation | constant | 0.800000 | 0.900000 | 0 | — | — |
| validation | constant | 0.900000 | 1 | 0 | — | — |
| validation | logistic | 0 | 0.100000 | 62155 | 0.032406 | 0.029266 |
| validation | logistic | 0.100000 | 0.200000 | 6114 | 0.139084 | 0.132974 |
| validation | logistic | 0.200000 | 0.300000 | 2005 | 0.243964 | 0.228928 |
| validation | logistic | 0.300000 | 0.400000 | 932 | 0.343041 | 0.298283 |
| validation | logistic | 0.400000 | 0.500000 | 492 | 0.443557 | 0.378049 |
| validation | logistic | 0.500000 | 0.600000 | 257 | 0.545089 | 0.439689 |
| validation | logistic | 0.600000 | 0.700000 | 136 | 0.645383 | 0.551471 |
| validation | logistic | 0.700000 | 0.800000 | 82 | 0.737856 | 0.609756 |
| validation | logistic | 0.800000 | 0.900000 | 35 | 0.835542 | 0.685714 |
| validation | logistic | 0.900000 | 1 | 17 | 0.949655 | 0.823529 |
| test | constant | 0 | 0.100000 | 92652 | 0.075992 | 0.048871 |
| test | constant | 0.100000 | 0.200000 | 0 | — | — |
| test | constant | 0.200000 | 0.300000 | 0 | — | — |
| test | constant | 0.300000 | 0.400000 | 0 | — | — |
| test | constant | 0.400000 | 0.500000 | 0 | — | — |
| test | constant | 0.500000 | 0.600000 | 0 | — | — |
| test | constant | 0.600000 | 0.700000 | 0 | — | — |
| test | constant | 0.700000 | 0.800000 | 0 | — | — |
| test | constant | 0.800000 | 0.900000 | 0 | — | — |
| test | constant | 0.900000 | 1 | 0 | — | — |
| test | logistic | 0 | 0.100000 | 77381 | 0.030515 | 0.022745 |
| test | logistic | 0.100000 | 0.200000 | 8161 | 0.140750 | 0.111383 |
| test | logistic | 0.200000 | 0.300000 | 3222 | 0.243887 | 0.184047 |
| test | logistic | 0.300000 | 0.400000 | 1698 | 0.343943 | 0.239694 |
| test | logistic | 0.400000 | 0.500000 | 944 | 0.445774 | 0.317797 |
| test | logistic | 0.500000 | 0.600000 | 592 | 0.544866 | 0.408784 |
| test | logistic | 0.600000 | 0.700000 | 345 | 0.646699 | 0.402899 |
| test | logistic | 0.700000 | 0.800000 | 204 | 0.743788 | 0.563725 |
| test | logistic | 0.800000 | 0.900000 | 76 | 0.839925 | 0.539474 |
| test | logistic | 0.900000 | 1 | 29 | 0.932357 | 0.758621 |

Calibration uses ten fixed equal-width bins [a,b), with probability 1 included in the last bin. Empty bins have missing rates. Compare mean predicted probability with observed rate in each nonempty bin; ECE weights absolute gaps by bin count. No recalibration is fitted on validation or test. The constant baseline's calibration can drift as cohort prevalence changes.

## Interpretation

Validation: logistic ROC-AUC 0.7905, AP 0.2492 versus constant AP 0.0530; Brier 0.0449 versus 0.0508. At the fixed top-5% budget, precision is 31.56%, lift 5.95. These are retrospective associations, not evidence that contacting customers causes purchases. Mean predicted probability is 5.85% versus observed prevalence 5.30%; the calibration tables quantify this gap.

Test: logistic ROC-AUC 0.8177, AP 0.2526 versus constant AP 0.0489; Brier 0.0421 versus 0.0472. At the fixed top-5% budget, precision is 30.91%, lift 6.32. These are retrospective associations, not evidence that contacting customers causes purchases. Mean predicted probability is 6.57% versus observed prevalence 4.89%; the calibration tables quantify this gap.

## Limitations and next evaluation dates

Do not finalize a model from four snapshots. Before another holdout examination, freeze an expanded rolling-origin protocol. Proposed weekly dates on available history: November 8/15/22, December 8/15/22, January 8/15/22, and February 8/15. Only use an earlier snapshot for fitting when its 14-day label window has fully ended before the evaluation date; overlapping weekly windows require explicit purging. These dates are proposals, not additional data used in this run. February 15's label window ends February 29 midnight, within current coverage. Additional later months should provide a fresh untouched holdout, broader seasonal coverage and customer-cluster-aware uncertainty estimates. The February snapshot has now been inspected and cannot serve as an untouched holdout for future tuning. Define contact cost, capacity and incremental business benefit before selecting an operating threshold. No such threshold is claimed here.

## Coefficients and reproducibility

Coefficients are on standardized log1p features, are conditional associations, and are unstable under correlated counts. No causal interpretation is justified.

| feature | standardized_log_coefficient |
| --- | --- |
| days_since_last_purchase | 0.487946 |
| purchase_sessions_30d | 0.028563 |
| sessions_30d | 0.004382 |
| view_events_30d | -0.266847 |
| cart_events_30d | 0.318668 |
| remove_events_30d | -0.062715 |
| purchase_events_30d | -0.059528 |
| distinct_products_30d | 0.478161 |
| days_since_last_event | -0.677703 |
| historical_purchasing_sessions | 0.349632 |

| metric | value |
| --- | --- |
| python | 3.11.16 |
| sklearn | 1.9.1 |
| numpy | 2.4.6 |
| pandas | 3.0.6 |
| duckdb | 1.5.6 |
| training_prevalence | 0.075992 |
| logistic_intercept | -2.872011 |
| iterations | 19 |

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/train_baselines.py
pytest
ruff check .
ruff format --check .
```

Aggregate CSVs are written to data/processed/phase-2.4/ (ignored by Git). The CLI accepts --database, --report, --output. No individual predictions or serialized models are exported, and existing datasets are preserved. The pipeline refits the same frozen specifications when rerun. Versions above record this run. No MLflow, LightGBM, deployment or storage migration is included.

API references: [LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) and [Average Precision](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html).
