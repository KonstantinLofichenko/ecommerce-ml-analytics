# GA4 suitability research — Phase 3.3

Status: **unexecuted BigQuery queries / INCONCLUSIVE decision**. See the
[assessment](../../docs/reports/phase-3.3-ga4-assessment.md) and
[execution manifest](execution-status.json). No production data or configuration is changed.

All SQL is GoogleSQL SELECT/CTE only. There are no persistent or temporary writes,
exports, credentials, or new dependencies. Schema-dependent statements are candidates:
they have not been BigQuery-parsed, dry-run, or executed. Run schema inspection first;
reconcile historical field availability before the other files. An execution failure
must be recorded, never interpreted as zero events.

## Access and safe execution

No `bq`, `gcloud`, local ADC file, Google Python package, or Google project environment
variables were found. This does not establish whether a browser account or remote
workload has access. No browser sign-in, account creation, API enabling, credentials,
or billing changes were attempted.

Minimum next steps, performed by the user: choose an existing authorized Google Cloud
project with BigQuery enabled; use BigQuery Sandbox without a billing account where
available. The executing principal needs permission to create query jobs in that
project and read the public dataset. A public dataset alone does not supply an
execution project. If none exists, account/project/API setup is a prerequisite;
this assessment stops before performing it. Never commit a credential file.

Use BigQuery Console with GoogleSQL. Start with `00_schema.sql`,
`00_nested_schema.sql`, and `00_volume.sql`. Select the dataset's actual location
in query settings (verify it in dataset details). Set named STRING parameters
`start_suffix=20201101`, `end_suffix=20210131` for full coverage. Inspect the validator's
bytes estimate before running. Initially use `20201101` for both suffixes for the
schema-dependent queries; label this as a one-day pilot, not full-period evidence.

If an already authorized `bq` CLI is available later, an example **dry-run only** is:

```bash
bq --project_id=YOUR_EXISTING_PROJECT --location=US query \
  --use_legacy_sql=false --dry_run \
  --parameter=start_suffix:STRING:20201101 \
  --parameter=end_suffix:STRING:20210131 \
  < analysis/ga4/sql/01_event_coverage.sql
```

Verify US is the dataset location before using this example. A dry-run validates
and estimates processing without executing the query. Do not remove `--dry_run`
until sandbox/free-quota availability has been verified. A maximum-bytes-billed
limit bounds a job's scan, **not** its dollar cost or accumulated monthly usage.
Do not execute on a paid project without explicit cost authorization. SQL `LIMIT`
is not a substitute for date/column scan restrictions.

For approved execution, retain job ID, location, SQL hash, parameters, dry-run
bytes, actual processed/billed bytes, cache-hit status and elapsed time per file.
Save only aggregate JSON results to `data/processed/phase-3.3-ga4/` (already ignored).
Update the execution manifest and report from actual results. Do not commit row-level
visitor IDs or full event exports. Start `06_exact_duplicates.sql` last: it reads
all fields and groups complete serialized event payloads.

## Query map and interpretation

- `00_*`: actual top-level/nested historical schema and per-table rows/logical bytes.
  Metadata statistics may lag; reconcile with actual `COUNT(*)` results.
- `01_event_coverage.sql`: all recorded names, daily/monthly and global aggregates,
  including total counts, identifier completeness, and UTC/property-date mismatch.
  A missing name in a completed full-period result means absent; an unexecuted
  query cannot establish absence. Required names are listed in the assessment.
- `02_identity.sql`: null, blank and explicit placeholder counts; integer-session
  extraction ambiguity. Inspect `07_parameters.sql` for string-typed session values.
- `03_session_quality.sql`: composite session counts, shared session IDs, midnight
  crossing, ties, multi-session visitors and pseudo-to-login identity conflicts.
- `03_sessions_funnel.sql`: cumulative presence and strictly chronological funnel;
  counts are sessions, across items, and equal timestamps cannot advance stages.
  Missing identity/session records remain in raw coverage but are excluded here.
- `04_purchases.sql`: event/transaction quality, conservative order scenario,
  monthly purchases, order-frequency and inter-order elapsed-day distributions.
- `05_snapshots.sql`: parallel unchanged event target and exploratory transaction
  target; no feature table or model. All four UTC snapshots have nominal 14-day
  windows. Actual timestamp coverage must confirm the bounds, including source-day
  timezone spillover. December 1/15 train; January 1 validates; January 15 holds out.
- `06_exact_duplicates.sql`: exact serialized payload multiplicities, retaining
  repeated-array order; detects cross-day identical content. It is a comparison,
  not a deduplication operation. No synthetic unique event ID is assumed.
- `07_parameters.sql`: actual parameter keys/types; intentionally unnests only for
  parameter-grain diagnostics, never for counting original events.

The known-placeholder filter rejects null, whitespace-only, `<Other>`, `NULL`, and
`(not set)` (case insensitive). It preserves original nonblank IDs. It cannot prove
that other obfuscated values represent real people. Extend the documented filter
only from measured evidence. `ga_session_id` must have exactly one positive integer
value; duplicate parameters are excluded even if their values agree. No global
session-ID uniqueness, midnight split, inactivity timeout, or cross-device stitching
is invented. Cross-session continuity is an observed pseudonymous proxy.

Candidate orders collapse repeated records with the same usable transaction ID
and visitor to their earliest observed timestamp, excluding IDs with ambiguous
visitor attribution or conflicting nonnull revenues. Missing revenues are reported
and not automatically rejected. Repeated IDs can represent retries or obfuscation;
this is a sensitivity scenario, not a verified order truth or permanent policy.
At a snapshot, this retrospective scenario can use later evidence to invalidate an
ID or collapse a repeated transaction back to its first timestamp. Therefore it is
**only a diagnostic**, unsuitable as production eligibility/features without a
point-in-time transaction-resolution rule. Event-target counts remain separate.
Refund events are counted but do not silently redefine completed purchases.

Queries do not output features. A later feature implementation must filter raw
UTC event times `< snapshot` before all aggregation and session counting, and use
only `[snapshot, snapshot + 14 days)` for labels. Whole-session future flags and
transaction IDs must never become predictive features.
