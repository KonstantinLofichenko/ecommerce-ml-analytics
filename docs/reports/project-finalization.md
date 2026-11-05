# Portfolio finalization audit — 5 November 2026

## Scope and outcome

The local working tree contains the completed analytics, V4 feature preparation,
scripted ML experiment and preserved notebook. Finalization reconciled entry-point
and architecture documentation, verified reproducibility without another real-data
experiment and prepared an explicit review/commit plan. No source data, dbt model,
feature/target definition, training code, model binary or dashboard was changed.
No commit or push was made during this task.

## Audit findings and resolutions

| Finding | Resolution / status |
| --- | --- |
| README described only V2.2 / three dashboard tabs | Updated current overview through V4.1 and the four documented analytical tabs, including retention. |
| Architecture had no V3/V4/ML end-to-end flow | Added the current raw → dbt → BI/ML → evaluation paths while retaining historical component details. |
| Notebook and scripted V4.1 configurations/results can be conflated | Separate linked result rows and reproduction guidance; original notebook/report/scripted evidence preserved. |
| Current uv lock differs from historical scripted runtime pins | Documented separate environments; verified the historical pinned setup in a clean temporary environment. Current lock also passes consistency checking. |
| Ruff now processes the historical notebook and verbatim Markdown code excerpt | Added narrow exclusions for those two preserved evidence files, not edits to their contents or blanket suppression of source-code linting. |
| Historical REES46 download paragraph referred to a nonexistent “link above” | Reworded the manual-data prerequisite without adding a new dataset download. |
| Local file links | No broken local file links or unresolved local heading anchors; both were checked after final edits. |
| Temporary `/tmp` dbt helper from earlier sessions no longer existed | Used a temporary credential-safe wrapper for checks; durable documentation uses the actual dbt CLI/profile, not `/tmp` dependencies. |
| Repository publication incomplete | The notebook, V4 source files, SQL, lock and scripted results are still pending review/commit. Local file links resolve, but documentation-only Git HEAD cannot reproduce untracked work. Include required evidence/source files in the approved final commits. |

## Executed checks

| Check | Actual result |
| --- | --- |
| Clean pinned environment | Created `/tmp/ecommerce-portfolio-repro` with Python 3.11.16; installed editable project `[dev,ml]` plus `requirements/ml-v41.txt` successfully. Existing .venv untouched. |
| Current lock consistency | `uv lock --check --offline` passed; no lock update or current-environment sync. |
| CLI dependency/import check | `scripts/train_repeat_purchase.py --help` succeeded in the isolated pinned environment. |
| Python tests | **87 passed, 3 skipped**, 5.83 seconds in the isolated environment. Skips are opt-in live migration integration tests. Tests include tiny synthetic fits, not another real customer experiment. |
| Real feature load / validation / maturity | Existing loader and splitter passed: 547,914 customers / 74,781 positives; train 122,467 / 16,361 positives; validation 78,700 / 11,287; test 33,020 / 4,440; excluded 313,727. No fitting or prediction on those rows. |
| Ordered feature-stream SHA-256 | `81fa12ff1b4c73078a9d321a6f60635dae99b13f5d5c1a54e34bfdc6746a3e62`, identical to the original scripted metrics record. |
| Trusted original artifacts | All three joblib models loaded under the pinned runtime. Two invented feature vectors produced finite normalized probabilities. No original validation/test rows were scored. |
| dbt parse | Passed with the existing catalog profile. |
| dbt tests | **281 passed**, no warnings/errors/skips, **22.91 seconds**, one thread against existing tables. No run/build/raw rebuild. |
| Ruff | Lint passed; format check passed for 116 non-excluded files. Frozen notebook/report exclusions are explicit in pyproject. |
| Preservation | All **147 protected files** matched pre-task SHA-256 values, including notebook, existing dbt/source/test/script files, experiment artifacts and original result reports. |
| Secret/large-file audit | 353 tracked/untracked nonignored candidates inspected before writing this report: no file over 2 MiB, no configured secret-value matches or private-key markers. This is not a universal secret-detection guarantee. |
| Git exclusions | Confirmed .env, virtual environments, raw/external datasets, processed metrics/models, notebook checkpoints and scratch outputs are ignored; intentional .env.example stays tracked. |

The notebook's original SHA-256 remains
`56c1ddbde7b35b8e858adaf2718d4bdc0ec288e988e073819bd17b0c0aa06378`.
Its recorded results were not recalculated. No predictions were written to
ClickHouse or Metabase and no experiment output was overwritten.

## Files changed in finalization

- `README.md`: current project summary, separate ML results, navigation, workflow,
  stack, locked development commands and historical dataset wording.
- `docs/architecture.md`: current integrated flow plus retained historical detail.
- `docs/reports/README.md`: index both completed ML records and this audit.
- `pyproject.toml`: narrow Ruff exclusions for immutable notebook/evidence excerpts;
  existing unrelated dependency edits remain intact.
- New `docs/project-reproduction.md`: isolated pinned versus current locked setup,
  service/data prerequisites, checks and explicit no-holdout-rerun boundary.
- New `docs/project-summary.md`: concise technical portfolio description and limits.
- New `docs/reports/project-finalization.md`: findings, actual checks and commit plan.

Existing uncommitted V4 files and dependency/README edits from earlier work were
preserved. No historical investigation report or executable evidence was deleted.
`.gitignore` already covers the current artifacts and needed no change. An unrelated
untracked `synerise_ml_fundamentals_ru.pdf` (115,124 bytes) appeared in the final
working-tree inventory; it was not edited or reviewed as project evidence and is
excluded from the proposed commits. The earlier secret scan did not include that file.

## Remaining limits and blockers

No code/test blocker was found for the documented **offline portfolio** scope.
Publication is blocked only on review and the pending commit/push authorization;
a clean checkout also requires separately provisioned services and local licensed
data for live database/training commands. Raw data and model binaries are intentionally
not downloadable from the Git repository itself.

Do not overstate the research evidence:

- Source timezone and uninterrupted collection remain unverified; first observed
  purchase is not necessarily first-ever purchase. Synerise's final raw load used
  count-only acceptance; earlier stronger experimental checks do not upgrade it.
- Labels use a later calendar date within 30 days, not orders or a 720-hour window.
  Maturity gaps exclude 313,727 customers. The seven-day test is one temporal fold.
- Notebook full-population EDA includes test-period labels. Saved code does not
  establish a perfectly sealed holdout or complete historical environment.
- The script preserves training-only preprocessing and validation-selected settings;
  its modest ROC-AUC/ranking improvement is not prospective business impact.
- Further tuning would need a fresh holdout and separately approved longer/rolling
  evaluation. No new algorithm, feature, tuning, orchestration or deployment was added.

## Proposed final commit plan — requires review

1. **Feature preparation and analytical provenance:** intended new V4 dbt models,
   shared macros, YAML and tests, feature documentation and the numbered SQL collection
   (historical inconsistent queries remain clearly separated).
2. **Reproducible offline experiments and evidence:** existing Python CLI/modules/tests,
   historical runtime pins, reviewed pyproject/uv.lock, original unchanged notebook,
   and the separate scripted report. Include every referenced dependency/source
   file; exclude data/processed artifacts and all credentials.
3. **Portfolio finalization documentation:** current README/architecture/report index,
   reproduction guide, concise summary and this audit. The previously approved
   notebook documentation commit remains intact; do not rewrite it.

Review the staged diff and repeat scoped checks against the exact staged contents
when commit authorization is given. Do not stage unrelated files automatically.
Do not push the earlier documentation-only commit as the complete portfolio by
itself. No commit or push is authorized by this finalization task.
