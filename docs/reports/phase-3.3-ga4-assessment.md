# Phase 3.3 — GA4 e-commerce dataset suitability assessment

Assessment date: 20 October 2026. **Decision: INCONCLUSIVE.** No authorized local
BigQuery execution path was found. No dataset queries or dry-runs were submitted.
Consequently, actual event counts, identity quality, repeat-purchase support and
label distributions are unknown. There is insufficient evidence to replace REES46
as the single source for both required tasks. Retain the existing source pending
measurement; this is not a finding that GA4 itself is unsuitable.

## Access and evidence

Inspected the existing architecture, dependencies and prior analytical reports.
The validated DuckDB reference and ClickHouse history support the current workflow;
Phase 3.2 has 20,692,840 reconciled raw events. Investigation artifacts are isolated
under `analysis/ga4/`. No database connections, service operations, configuration
changes, model training or data exports were performed for this assessment. AIS
was not accessed.

Local checks found no `bq` or `gcloud` executable, Google Python package, standard
application-default credential file, gcloud configuration directory, or Google /
BigQuery project environment variables. These checks do not rule out a separately
authorized browser or remote account. No such execution context was supplied or
used. No credential contents were searched or printed.

Google identifies the public sample as November 1, 2020–January 31, 2021 and
requires a Google Cloud project with BigQuery enabled. Sandbox is an option without
billing. The same documentation warns of placeholder values and limited internal
consistency. These are documentation findings, not measurements of this project's
query results. [Official dataset documentation](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset).

Minimum setup and dry-run commands are in [research instructions](../../analysis/ga4/README.md).
Choose an existing authorized project and verify Sandbox/free access. If account,
project, API activation or credentials are needed, stop for user setup. No billing
activation or paid execution is authorized by this research task.

## Event coverage

**All counts below are unknown, not zero.** Neither total events, distinct visitors,
daily/monthly distributions nor usable-identifier proportions could be measured.
`01_event_coverage.sql` will return every recorded name, not just the candidate list.

| Candidate recorded event | Actual count | Presence verified |
| --- | --- | --- |
| page_view | unknown | no |
| session_start | unknown | no |
| view_item | unknown | no |
| view_item_list | unknown | no |
| select_item | unknown | no |
| add_to_cart | unknown | no |
| remove_from_cart | unknown | no |
| view_cart | unknown | no |
| begin_checkout | unknown | no |
| add_shipping_info | unknown | no |
| add_payment_info | unknown | no |
| purchase | unknown | no |

A recorded event is tracking evidence, not proof of a completed business step.
An absent checkout/shipping/payment event must not be inferred from a purchase.

## Schema and identity

Actual historical schema inspection is blocked. The SQL bundle starts with
INFORMATION_SCHEMA top-level and nested-field inspection. Current documentation
must not be assumed to describe every field available in the 2020 export.
The following mappings are **expected candidates**, pending actual-schema validation.

| Field | Expected BigQuery type / shape | Proposed analytical use |
| --- | --- | --- |
| event_name, event_date | STRING | recorded step; property-calendar date |
| event_timestamp | INT64 | `TIMESTAMP_MICROS(event_timestamp)` for UTC ordering |
| user_pseudo_id, user_id | STRING, nullable | pseudonymous continuity / optional login audit |
| event_params | repeated RECORD, typed value members | correlated extraction, no event multiplication |
| user_properties | repeated RECORD, typed values | inspect only; not assumed point-in-time safe |
| items | repeated RECORD | separate item-grain relation with item offset |
| ecommerce | RECORD | transaction ID, purchase/refund revenue diagnostics |
| ecommerce.transaction_id | STRING | assess distinct orders and collisions |
| ecommerce.purchase_revenue, refund_value | FLOAT64 candidates | anomaly diagnostics; currency-aware conversion needed |
| event_params ga_session_id | value.int_value candidate | typed session component, not globally unique |

The documented export uses microsecond UTC timestamps, repeated parameter/item
records, and property-timezone event dates. Timestamp ties are possible.
[Export schema](https://support.google.com/analytics/answer/7029846).

Executable extraction examples are embedded in the supplied SQL. The session
expression accepts exactly one positive integer `ga_session_id`; duplicate keys
are flagged rather than arbitrarily selecting a value. Null, blank and known
placeholder IDs are rejected separately. Other synthetic IDs may remain plausible
but unusable for longitudinal analysis. Do not merge `user_id` and `user_pseudo_id`
without measuring their relationship. Cross-device person identity is unverified.

## Sessions and chronological funnel

No measured sessions, midnight crossings, missing-session rates, duplicate rates,
timestamp ties or cross-session continuity results are available. The identity,
session-quality and exact-payload duplicate queries cover these checks without
changing any source records. Composite `(visitor, ga_session_id)` keys group all
observed days together. Sessions can cross midnight or source tables; boundary
sessions remain potentially censored. No inactivity timeout is invented.

`03_sessions_funnel.sql` compares cumulative presence against strict sequence:
`page_view → view_item → add_to_cart → begin_checkout → purchase`. Each stage counts
a session once, across products. Earliest qualifying times establish sequence;
a later valid chain can qualify despite an earlier out-of-order event. Equal
timestamps never establish strict order. Missing steps stop the corresponding
chain, and purchase sessions missing required steps are reported separately.
Shipping/payment are optional and excluded until observed support justifies them.

| Metric | Result |
| --- | --- |
| Eligible composite sessions | unexecuted |
| Five cumulative presence stages | unexecuted |
| Five strictly ordered stages | unexecuted |
| Purchase sessions missing required steps | unexecuted |
| Timestamp tie / duplicate sensitivity | unexecuted |

These are session metrics, distinct from event counts and visitor conversion.
No event-name documentation alone can establish funnel feasibility.

## Purchases and repeat purchasing

All requested purchase measures are blocked: events, purchasing visitors, distinct
transactions, unusable/repeated transaction IDs, purchase frequencies, repeat
visitors, elapsed-day gaps, monthly activity, and refund/negative-revenue anomalies.
`04_purchases.sql` provides the corresponding aggregate diagnostics. No missing
measurement has been replaced with a number from another sample or blog.

Keep the original event-based 14-day target as one explicit scenario. Separately,
a candidate repeat-order definition uses two distinct usable transaction IDs for
the same usable visitor, with strictly later first-observed order times. Repeated
records for the same transaction do not establish another order. Exclude globally
ambiguous identity IDs and conflicting revenue IDs from this sensitivity scenario;
report exclusions. Tied times cannot prove later repeat orders. The gap output
reports these ties; inspect positive-gap support before claiming repeat behavior.

This conservative transaction resolution is retrospective research, not a safe
production eligibility rule: future duplicate/collision evidence can change which
historical candidate orders survive. A later production design would need explicit
point-in-time resolution and delayed-outcome policy. No target change is approved.
Obfuscated transaction continuity could defeat either interpretation.

## Candidate snapshots and validation

The proposed dates have nominally complete 14-day windows within published coverage.
Actual UTC bounds and daily-table completeness must still be confirmed: source-day
labels can use a property timezone, so documentation dates alone are insufficient.
`05_snapshots.sql` reports event and candidate-order scenarios separately.

| Snapshot UTC midnight | Role | Eligible | Positive | Negative | Rate | Maximum observed history | Label end exclusive | Identity completeness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2020-12-01 | train | unknown | unknown | unknown | unknown | 30 days | 2020-12-15 | unmeasured |
| 2020-12-15 | train | unknown | unknown | unknown | unknown | 44 days | 2020-12-29 | unmeasured |
| 2021-01-01 | validation | unknown | unknown | unknown | unknown | 61 days | 2021-01-15 | unmeasured |
| 2021-01-15 | holdout | unknown | unknown | unknown | unknown | 75 days | 2021-01-29 | unmeasured |

Eligibility requires a recorded purchase strictly before snapshot. Labels use only
`[snapshot, snapshot + 14 days)`. December training labels end before January
validation; validation labels end exactly at the January 15 holdout snapshot,
so the half-open windows do not overlap. No random row split is proposed. Freeze
settings before holdout inspection and fit future preprocessing on training only.

The SQL checks prior purchase presence and reports overlap with the first cohort.
Ever-purchaser event cohorts are nested: every earlier eligible visitor stays
eligible later. Thus any two-date shared count equals the earlier eligible count
under unchanged identity rules. This is returning-visitor evaluation, not independent
new-customer validation. Measure rates and both classes before considering modeling;
there is no defensible universal minimum sample count without a precision/power goal.

Only three months are available, spanning holidays; history is left-censored,
outcomes right-censored near the end, and many customers may have only one observed
purchase. More snapshots do not create independent customers or seasons. Identity
completeness among filtered cohorts is tautologically 100%; population completeness
must come separately from the raw purchase/identity audits. Report both denominators.

If repeat labels are too sparse/unreliable, a separate fallback is predicting a
first recorded purchase in the next 14 days for previously active nonpurchasing
visitors, with the same cutoffs and continuity audits. Its population, positive
counts and feasibility are also unmeasured. It requires explicit objective approval;
it cannot silently substitute for repeat-purchase prediction.

## Extraction and ClickHouse compatibility

This is a proposed representation, not a migration plan approved for execution.
Keep one event-grain record containing provenance, nullable original identifiers,
UTC `DateTime64(6)`, extracted audited parameters and original nested content
(e.g. serialized JSON). Keep item arrays intact or create a separate item relation
with an event occurrence key and item offset. Preserve raw typed-value members;
string/int/double parameter coercion must not silently discard evidence.

A content hash is not a unique event occurrence key: identical raw rows can be
legitimate or duplicate and must retain multiplicity. A later extraction would
need an immutable export manifest plus shard/row ordinal for transport identity,
not an invented GA4 event ID. Do not cross-UNNEST parameters and items in event
counts; that multiplies rows. Correlated parameter extraction preserves event grain.
Prices/revenue need explicit currency and precision assessment before choosing
Decimal; current FLOAT64 source evidence cannot be made exact by casting alone.

A bounded-memory design could read selected daily tables in paginated batches,
stream event and item outputs separately, and stage each immutable extraction
before publication. No full DataFrame/full dataset download is required. API page
order alone is not stable resumable identity; retain extraction/job provenance
and restart uncertain shards instead of blindly appending. No export was attempted.

Reconcile daily/global event and item counts, names, null/placeholder patterns,
UTC bounds, composite sessions, transaction multiplicities, revenue by currency,
and full-payload duplicate distributions. Define cross-engine canonical encodings
for nested arrays, floats, null versus empty and microseconds before checksumming.
Retain multiplicities. Compare proposed feature/label rows against BigQuery before
claiming equivalence to the reference analytical behavior.

## Cost and volume

No BigQuery jobs were submitted: **0 bytes scanned by this assessment; no query
charges incurred**. Dataset size, dry-run bytes, billed bytes, extraction duration
and ClickHouse storage are **unknown**. Local REES46 compressed storage is not a
valid proxy for nested GA4 storage.

`00_volume.sql` requests per-table metadata rows/logical bytes. Dry-run every query;
full-payload duplicate grouping is especially broad. Record per-job actual bytes,
cache status, elapsed time and aggregates. Query cost depends on project pricing
and remaining free quota; a scan cap does not guarantee free execution.
[Google cost controls](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)
and [Sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox).

Future estimates should report projected bytes per selected day/column, multiply
by the exact date range and include repeated scans. Estimate runtime/storage only
from an authorized bounded pilot (processed bytes, elapsed time, serialized and
compressed bytes), with uncertainty. No dollar/runtime/storage estimate is invented.

## Comparison and decision

| Requirement | Existing REES46 evidence | GA4 assessment |
| --- | --- | --- |
| Historical source | 5 months, 20,692,840 reconciled events | documented 3 months; actual volume unknown |
| Funnel | measured view/cart/purchase sequence | richer candidate sequence; presence/order unknown |
| Identity / sessions | measured composite keys and exclusions | obfuscation risk; continuity unmeasured |
| Repeat task | 243,162 validated customer snapshots | purchasing support/labels unknown |
| Transactions | purchase events lack order IDs | candidate transaction field; reliability unknown |
| Storage | validated DuckDB/ClickHouse reference | nested mapping proposed, no migration |

Local comparison evidence: [migration report](phase-3.2-migration.md),
[behavior report](phase-1.2-october-2019.md) and
[baseline report](phase-2.4-baselines.md). The baseline report records the implemented
event-based labels; these should not be confused with older purchasing-session
feasibility counts.

**INCONCLUSIVE** is the only supported category. Do not replace REES46 now. A later
GO requires measured strict funnel support, defensible longitudinal identities,
usable repeat outcomes across chronological splits, and affordable reproducibility.
A CONDITIONAL GO must name restrictions or obtain explicit approval for a different
ML objective. Measured failure of either required task would support NO-GO for the
single-source replacement, even if the funnel alone is attractive.

## Reproducibility and checks

Created only this report and `analysis/ga4/` instructions, SQL and machine-readable
execution status. Every query is marked **unexecuted**; none has a job ID, scan
estimate or measured result. Local structural checks verify bounded suffix filters
on event scans, SELECT-only statements, manifest/file correspondence and valid JSON.
These checks are not BigQuery syntax/type validation or evidence of dataset behavior.
No Python runtime code or dependencies were added; SQL still requires authorized
BigQuery dry-runs and execution before results can be accepted.
