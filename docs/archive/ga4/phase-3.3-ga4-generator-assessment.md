> Historical archive: this document records an earlier investigation or proposal.
> It does not describe current deployment state. See the [current funnel contract](../../funnel-data-contract.md).

# Phase 3.3 follow-up — ec_demo generator assessment

Assessed 20 October 2026 at upstream commit
`4f5c09c6965e76662d31bc8e3a9ef68e74599bb0`.

**Recommendation: CONDITIONAL GO for an explicitly synthetic engineering/demo
track; NO-GO as the sole evidence source for realistic repeat-purchase modeling.**
It generates repeat purchases and long enough histories to exercise the pipeline.
Its repeat behavior is driven by hand-written sampling rules, not an empirically
validated customer lifecycle. Do not replace REES46 on this evidence. This is a
separate local generator, not a downloadable copy of Google's observed public GA4
sample; the public sample's access-limited assessment remains INCONCLUSIVE.

## What was actually run

Downloaded the source into `/tmp`, inspected generation/identity/utility code, and
ran the unmodified generator with its checked-in January 1–March 31, 2025 date
range, 1,000 persons and seed 42. Only the output directory was changed. Generation
used a separate temporary Python environment with PyYAML 6.0.3; the BigQuery loader
and client were not needed. Local DuckDB analysis used temporary relations only.
No project datasets, credentials, infrastructure or earlier results were changed.
No model was trained. There were no cloud jobs or cloud query charges.

Artifacts: [execution manifest](../../../analysis/ga4/generator/run-manifest.json),
[configuration](../../../analysis/ga4/generator/evaluated-config.yaml),
[aggregate results](../../../analysis/ga4/generator/results-seed-42.json),
[evaluator and reproduction](../../../analysis/ga4/generator/README.md).
All figures below are measured from this single run, unless marked code inspection.
The source README's approximate counts are not substituted for measured output.

## Measured output and history

| Metric | Measured |
| --- | --- |
| Daily event files | 90 |
| Recorded events | 285,408 |
| Output JSONL and CSV bytes | 686,705,299 (~655 MiB) |
| Generated persons (configuration) | 1,000 |
| Distinct observed device/pseudo IDs | 1,109 |
| Customer-master / observed login IDs | 308 / 308 |
| Orders / distinct order IDs | 1,563 / 1,563 |
| GA4 purchase events / distinct transaction IDs | 1,440 / 1,440 |
| GA4 purchasing login IDs | 303 |
| Login IDs with at least two GA4 purchase events | 285 (94.1% of purchasers) |
| Median GA4 purchase events per purchasing login ID | 5 |
| Median elapsed gap between login-level purchases | 8.48 days |
| Median first-to-last purchase span per purchasing login ID | 50 days |
| Order customers / repeat order customers | 305 / 287 |
| Median elapsed gap between customer orders | 8.08 days |
| Median observed event span per pseudo ID | 81 days |
| Pseudo IDs with at least 60 days between first/last event | 1,030 |

There is genuine continuity *within the simulation*: identities are retained across
days and purchases receive distinct transaction IDs. Multiple purchases are not
merely repeated item lines from one order. This is enough data to test cutoffs,
aggregation, label construction and pipeline reconciliation. A first-to-last span
is not continuous activity or proof of complete tracking.

UTC event bounds were 2024-12-31 11:20:47.413302 through
2025-03-31 10:58:21.039750. Generation dates use `Pacific/Auckland`; local-date file
names are not UTC partition dates. The four proposed label windows end before the
observed tail, with approximately 30/44/58/72 days of initial historical coverage.
All history begins within the simulated window; customer registration dates and
synthetic first-touch values do not supply earlier behavioral events.

## Does it produce realistic repeat purchases?

**It produces repeat purchases; realism is unproven and materially limited.** Code
inspection found these mechanisms:

- Every day samples a fixed number of persons uniformly without replacement from
  the same population, adjusted for weekday and configured campaigns. It does not
  condition return timing on last purchase, replenishment, churn or customer tenure.
- Each person keeps a Beta(2,5) propensity. This enters add-to-cart probability as
  an additive `0.2 * propensity` adjustment; it is not a fitted repeat-purchase hazard.
- Session-count segments (new, returning, loyal) increase funnel probabilities.
  All customers can accumulate loyalty under these rules without a purchase-driven
  lifecycle. History can predict the programmed segment rather than observed demand.
- Guests and account sessions without the allowed login/noise condition cannot
  enter the main `select_item`/`view_item` funnel, not just checkout. This creates
  an artificial relationship between browsing depth, account status and purchasing.
- Each qualifying session can generate at most one order; there is no persistent
  basket/replenishment state, purchase cooldown or evidence of empirical calibration.

These are substantive design limitations, not a claim that any particular repeat
rate is impossible in every store. The 51–56% login-level 14-day rates below are
much higher than the existing REES46 event-target baseline's roughly 5–10%; the
datasets/populations differ, so that comparison is a warning about transferability,
not a statistical realism test. Without a real reference distribution, plausible
looking intervals cannot establish realistic or useful predictive difficulty.

Implementation evidence:
[persistent identity/propensity](https://github.com/ajaxbarcelonacruyff/ec_demo/blob/4f5c09c6965e76662d31bc8e3a9ef68e74599bb0/src/identity.py),
[daily sampling, login gate and funnel rules](https://github.com/ajaxbarcelonacruyff/ec_demo/blob/4f5c09c6965e76662d31bc8e3a9ef68e74599bb0/src/user_journeys.py).

## Four measured 14-day snapshots

Keep the existing event target: eligible if a recorded purchase precedes midnight
UTC; positive if a recorded purchase occurs in `[snapshot, snapshot + 14 days)`.
No inferred order is inserted to repair missing GA4 purchases. Login-based figures
use only the `user_id` actually present on purchase events; no future identity
stitching is performed.

| Snapshot UTC | Role | Eligible login IDs | Positive | Negative | Rate | Label end exclusive |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-02-01 | training | 205 | 110 | 95 | 53.66% | 2025-02-15 |
| 2025-02-15 | training | 253 | 130 | 123 | 51.38% | 2025-03-01 |
| 2025-03-01 | validation | 281 | 154 | 127 | 54.80% | 2025-03-15 |
| 2025-03-15 | holdout | 295 | 166 | 129 | 56.27% | 2025-03-29 |

Training outcome windows finish by the validation snapshot. Validation outcomes
finish at the holdout snapshot; half-open windows prevent overlap. Customers repeat
across all splits: under ever-purchaser eligibility, earlier cohorts are subsets
of later ones. There are only 303 purchasing login IDs overall; 1,034 snapshot rows
are not 1,034 independent customers. This is sufficient for software exercises,
not strong temporal generalization evidence.

Identity changes the answer substantially:

| Snapshot | Pseudo-ID eligible / positive | Order-customer eligible / positive |
| --- | --- | --- |
| 2025-02-01 | 229 / 101 | 217 / 121 |
| 2025-02-15 | 297 / 130 | 260 / 135 |
| 2025-03-01 | 342 / 155 | 288 / 165 |
| 2025-03-15 | 370 / 168 | 300 / 177 |

Order-customer counts use the separate order ledger and are a different source
scenario, not the unchanged GA4 event target. The private simulator person graph
is not exported as an event-level person key; pseudo IDs can merge people or split
one person's devices. Choose an explicit observed identity policy before any use.

The CLI can generate more months and persons, so insufficient *length* is fixable.
A more useful synthetic benchmark could use 6–12 months, a burn-in interval, larger
cohorts and multiple seeds/scenarios. Longer runs alone do not fix realism,
independence or lifecycle deficiencies. No larger run was performed here.

## Identity and data-quality findings

- No null pseudo IDs or session IDs were observed. Login IDs were absent on
  217,991 of 285,408 events (76.4%), but **none** of the 1,440 purchase events.
  Account IDs being optional on browsing does not imply guest purchasing support.
- 36 pseudo IDs were associated with multiple observed login IDs. Multi-device
  and shared-device behavior is intentionally generated; device identity is not
  customer identity. Session counts must use composite identity/session keys.
- 1,098 pseudo IDs had changing `user_first_touch_timestamp` values. Source code
  sets later-session first touch using a newly sampled 1–90-day offset rather than
  retaining one stable first touch. Do not use it as customer age/history evidence.
- 123 of 1,563 orders (7.87%) had no matching GA4 purchase event. Session-level
  tracking noise preserves orders while suppressing commerce events, and separate
  per-event loss can drop purchase events. The missingness is part of the generator,
  so the README's simple one-to-one order/purchase claim does not hold for this run.
- There were 57 observed refunds. Final `orders.status` includes later refund
  outcomes; it must not enter historical features without as-of reconstruction.
  Pending refunds outside the generation range are censored.
- No duplicate customer-master IDs occurred in this run. However, account IDs are
  sampled as random six-digit values without a uniqueness check in `utils.py`.
  Increasing population can introduce artificial customer collisions.

Timestamp/ID evidence:
[utilities](https://github.com/ajaxbarcelonacruyff/ec_demo/blob/4f5c09c6965e76662d31bc8e3a9ef68e74599bb0/src/utils.py),
[order and refund generation](https://github.com/ajaxbarcelonacruyff/ec_demo/blob/4f5c09c6965e76662d31bc8e3a9ef68e74599bb0/src/generate.py).

## Funnel suitability

The desired five-step chronological funnel is present and measurable. Across
29,838 observed composite sessions, cumulative presence and strict chronological
results were identical in this run:

| Cumulative stage | Presence sessions | Strictly ordered sessions |
| --- | --- | --- |
| page_view | 29,834 | 29,834 |
| → view_item | 5,656 | 5,656 |
| → add_to_cart | 2,288 | 2,288 |
| → begin_checkout | 1,724 | 1,724 |
| → purchase | 1,337 | 1,337 |

Counts are across items, one conversion per session, with strictly increasing UTC
timestamps; equal timestamps cannot advance a stage. Purchase events outside a
complete observed chain remain purchase events for labels. There were also 1,436
shipping-info and 1,451 payment-info events. All 20 observed event names/counts are
in the aggregate JSON, including logout (the README advertises 19 types).

This supports SQL/demo development. Because sequences are emitted by programmed
ordered journeys, presence equaling chronology is not evidence that the pipeline
can handle all real-world tracking anomalies. Separate adversarial synthetic tests
remain necessary for ties, duplicates, reversed events and boundary sessions.

## Reproducibility and validation

Upstream **42 tests passed** locally. The added evaluator boundary test passed,
covering strict prior eligibility, exact snapshot inclusion, exact 14-day exclusion,
nonpurchase events and missing login IDs. Ruff lint and format checks passed for
the research Python files. These tests validate implementation behavior, not
statistical realism. The generator itself was not changed.

The random seed does not control transaction identifiers: `uuid.uuid4()` supplies
them. Exact output bytes are therefore not guaranteed on rerun, even if behavioral
aggregates repeat under the pinned code/environment. Daily output streams to disk,
but the upstream generator retains all order dictionaries until final CSV writing;
large-scale generation is not fully bounded-memory. A new output directory is
necessary when changing a run's date range because obsolete files are not cleared.

## Decision for this portfolio

Use it if the deliverable is explicitly a **synthetic GA4 engineering demonstration**:
nested JSON ingestion, event/item separation, identity audits, funnels, reconciliation
and leakage-safe labeling. Preserve provenance, noise settings and simulated-target
limitations. Synthetic model metrics would assess recovery of generator rules,
not real-customer predictive performance.

Do not adopt it as the sole replacement for the current evidence-based repeat-task
portfolio. Before that could be justified, it would need calibrated return hazards,
acquisition/churn and purchase-dependent history, repaired identifiers/first-touch,
point-in-time ledger semantics, multiple independent seeds, and comparison against
real held-out customer behavior. Increasing users or duration cannot substitute for
those checks. No migration or target change is recommended from this assessment.
