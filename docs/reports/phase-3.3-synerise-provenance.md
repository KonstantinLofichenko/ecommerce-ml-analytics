# Phase 3.3 follow-up — Synerise provenance and timestamp verification

Investigated 21 October 2026. **CONDITIONAL GO for architecture planning and
reproducible offline research using the pinned archive and explicit source-clock
semantics.** Neither unresolved issue by itself prevents that limited scope.
They do prevent claims of verified UTC timing, exact physical elapsed-time labels
across unknown clock changes, or equivalence to the published challenge corpus.
No migration, primary-dataset switch, infrastructure implementation or training
was performed or is approved by this report.

## Findings at a glance

- **Verified:** the existing archive, all six archived member payloads and all six
  extracted files match the original SHA-256 manifest. Fresh counts and timestamp
  bounds exactly reproduce the earlier assessment.
- **Verified:** the reference table was present in March 2025 and remains in the
  current official README. Raw and preprocessed datasets are distinct published
  variants. No visible release/tag documents the current archive's larger counts.
- **Unresolved:** why the linked archive contains 225,224,262 events rather than
  the reference 168,900,513. A later modification date is not an explanation.
- **Unresolved:** source timezone and the timestamp preparation/rounding process.
  Activity patterns, generic platform documentation and naive parsing cannot
  establish UTC or a specific local zone.

## Archive identity and integrity

Reused `data/external/synerise/synerise_dataset.tar.gz`; no second archive was
downloaded. Original official link:
[synerise_dataset.tar.gz](https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz),
linked as the original Synerise dataset by the
[dataset page](https://recsys.synerise.com/data-set).

Archive bytes: **2,062,884,710**. SHA-256:
`e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7`.
The existing manifest matches a fresh complete archive hash. Each archived payload
was streamed and independently compared with its expected member SHA-256. Extracted
files were hashed before and after diagnostics; all six match. This verifies local
integrity and extraction consistency, not a publisher-signed release identity.

| File | Bytes | Rows | Row groups | Repeated full-group signatures |
| --- | --- | --- | --- | --- |
| page_visit.parquet | 2,010,901,793 | 199,451,980 | 191 | 0 |
| search_query.parquet | 352,048,335 | 13,223,769 | 13 | 0 |
| add_to_cart.parquet | 105,425,078 | 7,541,117 | 8 | 0 |
| remove_from_cart.parquet | 36,530,822 | 2,688,894 | 3 | 0 |
| product_buy.parquet | 31,512,514 | 2,318,502 | 3 | 0 |
| product_properties.parquet | 67,363,395 | 1,534,050 | 2 | 0 |

Exactly six regular files, one per named source, occur in the archive; no extra
historical partitions/input/target directories are present. Source files have
different byte hashes. There are **220 physical row groups** in total, normally
1,048,576 rows each, with smaller final groups. Full-group row counts and tuple-hash
sum/XOR signatures found no repeated groups within a file. This is a limited check
for obvious repeated segments; it does not rule out partial copied segments,
changed copies or existing duplicate rows. No source deduplication occurred.

All event sources and many row groups cover overlapping June–December periods.
For example, the first two page groups both span almost the entire period. Thus
physical row groups are not disjoint daily partitions; summing date-range lengths
would double-count coverage. Overlap alone is not duplicated events, especially
between different event types. We counted rows, not partition date lengths.

Every remeasured event bound matches the previous assessment. All-source bounds
are **2022-06-23 00:10:00–2022-12-08 00:09:59**, source clock. Per-file minima/maxima
are retained in [verification.json](../../analysis/synerise/provenance/verification.json).
No change from the prior measured dataset was found.

## Published versus measured counts

| Event | Published | Reverified | Difference | After exact-row deduplication (comparison) |
| --- | --- | --- | --- | --- |
| page_visit | 150,713,186 | 199,451,980 | 48,738,794 | 178,752,573 |
| search_query | 9,571,258 | 13,223,769 | 3,652,511 | 12,606,626 |
| add_to_cart | 5,235,882 | 7,541,117 | 2,305,235 | 7,379,624 |
| remove_from_cart | 1,697,891 | 2,688,894 | 991,003 | 2,535,306 |
| product_buy | 1,682,296 | 2,318,502 | 636,206 | 1,937,599 |

The published values come from the official repository's event-count table, not
our environment and not a demonstrated release checksum. The archive counts come
from fresh full-file `COUNT(*)`, agreeing with Parquet footer rows and prior scans.
The reference total is **168,900,513**; the local total is **225,224,262**.

Exact-row deduplication alone cannot account for the difference: even the comparison
unique-row counts exceed all five references. A single common earlier end cutoff
alone cannot reproduce the table either. Cumulative counts from the matching prior
daily aggregates cross the five references on different, nonoverlapping dates:

| Event | Reference count reached within source date |
| --- | --- |
| page_visit | 2022-11-06 |
| search_query | 2022-11-02 |
| add_to_cart | 2022-11-01 |
| remove_from_cart | 2022-10-27 |
| product_buy | 2022-11-04 |

This rules out a shared historical prefix as the sole transformation. It does not
rule out time restrictions combined with customer filters, selection rules,
changed anonymization, different records or other unpublished preprocessing. No
specific one of those possibilities has been verified.

## Evidence about versions and publication dates

1. The [official data page](https://recsys.synerise.com/data-set) explicitly offers
   original data and a separate preprocessed competition variant. The latter
   restricts input time, supplies targets and a selected one-million-client list;
   this is not evidence of a versioned chronological release history for the raw
   archive. We did not download that second dataset.
2. The exact reference table is in the
   [March 10, 2025 README](https://github.com/Synerise/recsys2025/blob/6015ed45030aab9502f80702b229f9ec10c04c61/README.md) and unchanged in the
   [current pinned README](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/README.md).
   It appears in the general dataset section, alongside the distinction between
   all recorded interactions and selected submission clients. There is no basis
   to relabel it as counts for exactly one million clients.
3. All 11 visible repository commits were inspected. The latest is July 31, 2025,
   adding hidden tasks; README/split history contains no explanation of a raw-data
   count revision or timezone normalization. Public
   [releases](https://github.com/Synerise/recsys2025/releases) and
   [tags](https://github.com/Synerise/recsys2025/tags) APIs returned empty lists.
   This means none are currently visible, not proof that no artifact ever changed.
4. A fresh HEAD response reports the same 2,062,884,710-byte length, ETag
   `0x8DE21E72E378736` and Last-Modified **2025-11-12 12:29:52 GMT** as the earlier
   observation. It is an object-store modification timestamp, not a semantic
   release note or content checksum. No current complete remote payload was fetched.
5. Tar member modification times are **August 18, 2025, 10:53:28–10:53:30 UTC**;
   the five event files identify `parquet-cpp-arrow version 20.0.0` as producer,
   while product properties identify version 19.0.1.
   These metadata dates postdate the competition period, but can result from
   rewriting, copying or packaging unchanged records. They do not prove which
   rows changed or why the published counts differ. Archive/upload metadata times
   must not be confused with the 2022 event timestamps.
6. All 13 visible issue/PR entries and the four comments on the three entries with
   comments were inspected. [Issue 5's maintainer response](https://github.com/Synerise/recsys2025/issues/5#issuecomment-2808612853)
   explains internal splitting versus unsplit submission inputs, not count changes.
   [Issue 1](https://github.com/Synerise/recsys2025/issues/1) concerns active-client
   embedding filtering; the other issue topics do not answer provenance/timezone.
   Repository metadata has discussions disabled. These checks do not cover private
   correspondence or inaccessible competition support channels.

The [official challenge site](https://www.recsyschallenge.com/2025/) also lists
approximately the reference event sizes and about 19 million users, rather than
providing a checksum mapping them to the current archive. **Version explanation
remains unresolved.** We can identify a local artifact precisely but cannot assert
that it is identical to the original competition corpus. The exact five-count
historical table is not explained by archive Last-Modified alone.

## Authoritative timezone and preparation evidence

The inspected official pages describe date/time strings, without an offset or
IANA zone. Actual Parquet fields are VARCHAR, not timezone-bearing timestamps.
The repository does not ship the raw event export/anonymization preparation code.
Its documented anonymization of names/query embeddings and price buckets does not
establish a timestamp anonymization rule.

[split_data.py](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/data_utils/split_data.py)
uses `pd.to_datetime` without `utc=True`, `tz_localize` or `tz_convert`. It resets
derived target-boundary hour/minute/second to midnight, then compares values on
that same clock. That resets a **cutoff**, not original event timestamps. No code
there establishes UTC, rounds event values or resolves DST folds. Its final target
endpoint can be a partial day; our existing offline snapshots already avoid that
boundary. Current code/history keyword checks found no source-event timezone or
rounding implementation.

Generic Synerise [Jinjava platform documentation](https://hub.synerise.com/developers/inserts/filter/#timestamp_to_time)
discusses UTC Unix timestamps and output-timezone formatting. This corpus contains
formatted date strings with unknown export history, not documented raw Unix epochs.
That platform page is **insufficient evidence for this dataset's timezone**.
Publisher headquarters, an evening activity peak and a conventional SQL string
format are also insufficient. UTC versus a particular local timezone remains
unresolved; so does whether different events share a consistently normalized clock.

## Independent clock diagnostics — measurements, not timezone identification

All timestamps have whole-second representation and parse successfully. This is
storage precision, not evidence of second-accurate physical ordering.

| Event | Seconds divisible by 5 | Peak source hour | Lowest source hour |
| --- | --- | --- | --- |
| page_visit | 96.66636% | 19 | 2 |
| search_query | 96.66477% | 19 | 2 |
| add_to_cart | 96.66950% | 19 | 2 |
| remove_from_cart | 96.66376% | 19 | 2 |
| product_buy | 96.66561% | 19 | 2 |

Interior-date hourly peaks are 19:00–19:59, minima 02:00–02:59 across event types.
The two partial boundary dates were excluded for hourly/weekday comparisons.
Most activity types peak on Sunday after normalizing per observed weekday; purchase
activity peaks on Monday. Monthly peaks vary (purchase peaks include 09:00/10:00
in some months). None uniquely establishes a timezone or a DST conversion.

Daily event volumes are positively correlated across event types (Pearson
**0.824–0.987** over 167 interior dates). October 23 shows simultaneous increases
relative to October 22: about +50% page, +79% search, +57% remove and +61% buy.
This may reflect common demand, collection or preprocessing effects; it is not
proof of a timezone shift, campaign or timestamp anonymization. Partial final-day
volumes must not be interpreted as a retailer demand collapse.

All five sources begin around June 23 00:10 and stop within December 8 00:00–00:09.
There are 169 source dates, with all 24 hourly bins represented on the first date
but only hour 00 on the last. Exact source-type minima differ slightly. These
aligned boundary clips suggest a common selection boundary, but its rationale
and absolute-time interpretation are unknown. No timestamps were moved to midnight
or shifted to make calendar windows appear complete.

Strong five-second clustering is verified, while non-multiple-of-five events also
exist. Rounding, truncation, anonymization or upstream batching are hypotheses;
the particular mechanism and pre-rounding precision are unverified. Ties cannot
establish chronological order. Row groups span long overlapping ranges and their
physical order is not a documented chronological event sequence, so row-order
reversals cannot diagnose DST on their own.

Purchases near snapshot boundaries demonstrate that relabeling source midnight as
UTC midnight without evidence can matter:

| Source snapshot | Purchase rows within ±1 hour | Distinct clients | Purchase rows within ±1 hour of label end | Distinct clients at label end |
| --- | --- | --- | --- | --- |
| 2022-08-01 00:00:00 | 237 | 71 | 166 | 75 |
| 2022-09-01 00:00:00 | 352 | 92 | 149 | 65 |
| 2022-10-01 00:00:00 | 139 | 53 | 168 | 89 |
| 2022-11-01 00:00:00 | 169 | 127 | 384 | 205 |

These are raw row/client proximity counts in `[boundary−1 hour,boundary+1 hour)`,
not observed label flips. They include clients who may be ineligible or positive
for other reasons; no alternate timezone label result is claimed.

## Consequences for funnels and elapsed windows

A single unknown **constant offset**, applied consistently to all events and
cutoffs, leaves order and time differences unchanged. Merely lacking the offset
does not make a strict page→cart→buy source-clock comparison invalid. Ties and
coarse timestamps create genuine ordering ambiguity separately from offset
ambiguity. Keep strictly increasing times and retain presence-versus-order audits.

If the strings are local wall times crossing DST, or if sources/devices use
inconsistent clocks, physical elapsed time and order around a clock change can
be ambiguous. A repeated fall-back wall time cannot be resolved from a naive
string. We have no evidence sufficient to resolve or exclude that situation.
This qualifies the earlier assessment's statement that ordering is valid: it is
valid **on the represented source clock**, not proven physical-time ordering.

| Analysis | Unknown constant offset | Unknown DST or inconsistent source clocks |
| --- | --- | --- |
| Strict funnel order | Unchanged if one shared clock | May be wrong/ambiguous near clock changes |
| One-/seven-day numeric gap | Unchanged by a common translation | Not guaranteed 24/168 physical hours |
| Same-day counts | Source-date reproducible; local/UTC day unknown | Calendar interpretation also uncertain |
| Derived inactivity session | Constant translation leaves gaps unchanged | Folds/jumps can split or join activity |
| Midnight-based session split | Depends on chosen day convention | Particularly sensitive; not a real session ID |

We did not create derived sessions. Calendar/day-of-week/hour features must be
labeled **source-clock**, not customer-local or UTC. A 24-hour gap window is not
the same as “same calendar day,” even when timezone is known.

## Consequences for 14-day repeat purchasing

Existing snapshots remain reproducible under `timestamp < t` historical eligibility
and `[t,t+14 days)` labels, with t explicitly source-clock midnight. The existing
August–November cutoffs have full observed source-clock follow-up and avoid the
partial December tail. Positive/negative counts have not been changed.

A common fixed offset with cutoffs translated too leaves labels and split ordering
unchanged. Choosing **new UTC-midnight** cutoffs instead of those translated source
midnights is a different experiment and can change eligibility/features/labels.
Do not attach `Z` to these strings and call that a verified conversion.

Numeric 14-day arithmetic represents 336 source-clock hours. Calling those 336
physical elapsed hours requires a stable common clock or resolved timezone/DST
semantics. Calendar-local “next 14 days” can differ from 336 hours across DST.
Unknown timezones do not automatically introduce future-feature leakage when every
comparison uses one explicit clock, but cross-source clock inconsistency could
invalidate that assumption. Train/validation/test cutoffs and horizon ends must
remain on the same convention; no mixing source dates with UTC service timestamps.

Recommended convention for the offline research protocol:

- Preserve raw timestamp strings and a timezone-naive `event_time_source` value.
- Record `source_timezone_status=unverified`, source checksum and clock-policy
  version with every derived run. Display source-clock dates without a UTC suffix.
- Keep feature cutoffs strict and label windows half-open, with raw-event scope
  applied before aggregation. Source-clock calendar features must be named so.
- Treat physical-elapsed-time, UTC-midnight and retailer-local interpretation as
  unresolved. No arbitrary timezone localization or conversion.
- On publisher clarification, create a new derived clock-policy version and
  reconcile changed boundaries/labels; do not silently reinterpret old results.

## Decision, remaining uncertainties and next actions

**CONDITIONAL GO to architecture planning**, with these explicit limits accepted
at review. Hash-pinned local reproducibility, unchanged counts and sizeable
longitudinal cohorts permit offline research on this artifact. Neither an unknown
fixed offset nor mismatch against an undocumented historical count table proves
that the data is unusable. Conversely, neither can simply be declared resolved.

Outstanding publisher questions: count-version/filter mapping; intended original
research archive and official checksum; shared timezone/DST treatment; timestamp
rounding/shifting/anonymization and boundary construction. These block claiming
canonical challenge equivalence or verified UTC/physical-time deployment semantics.
They need not block planning a research system that preserves the uncertainty.
The prior order/session, static-attribute, identity and NonCommercial limitations
remain applicable; this follow-up does not remove them.

Review the [unsent publisher inquiry](../archive/synerise/phase-3.3-synerise-publisher-inquiry.md) and
approve contact separately if desired. Official contact was taken from the README;
no email or GitHub issue was sent/created. Do not begin migration or implementation
until review and explicit approval.

## Reproduction, checks and preservation

[Research instructions](../../analysis/synerise/provenance/README.md), verifier,
summary script, boundary SQL/results and public-source metadata are under
`analysis/synerise/provenance/`. Verification completed in 35.49 seconds
with a 2 GB DuckDB working-memory cap and two threads. It used the existing archive
and Parquet only; no second data download, extraction, source rewrite or model run.

Local checks passed: archive SHA, six archive member and extracted-file hashes,
pre/post source hash equality, fresh/footer/prior count agreement, row-group row
coverage and all hourly/second/minute/weekday count conservation. The two existing temporal
boundary tests passed; Ruff lint/format and whitespace checks passed. Row-group signatures are limited
noncryptographic multiset diagnostics; source-file identity uses SHA-256. No
customer-level data was exported. No existing databases, REES46 results, Docker
resources, credentials, AIS artifacts, commits or pushes were changed.
