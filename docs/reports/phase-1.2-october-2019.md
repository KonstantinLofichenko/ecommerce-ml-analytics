# Phase 1.2 — Customer behavior and funnel exploration

Source: `data/raw/2019-Oct.csv`. All source rows are analyzed. UTC is used throughout.

## Measured findings

- 4,102,283 events; 399,664 known customers; 25,762 purchasing customers.
- 2,709 customers have multiple recorded purchasing sessions; 2,492 purchase on multiple UTC days.
- 22 session IDs are shared by multiple known customers. Selected session key: `(user_id, user_session)`; 873,960 raw session IDs become 873,984 analytical sessions.
- 637 events with missing session IDs are excluded only from session/funnel metrics, not customer or raw-event counts.
- Presence funnel: 826,170 → 190,750 → 20,487 sessions. Strict chronological funnel: 826,170 → 178,355 → 19,410.
- 213,155 excess exact duplicate rows; see the scenario comparison below.

Observed inter-purchasing-session gaps: 3,564; median 6.210567 days, p90 18.516104 days.

Strict chronological view-to-purchase conversion is 2.35% among sessions with a timestamped view; presence conversion is 2.48% among sessions with a recorded view.

For 7-day follow-up, 23,127 purchasing-session anchors have full coverage; 1,646 have a strictly later repeat within the horizon. 16,380 anchors also have equally long observed history. These are purchaser-only feasibility counts.

For 14-day follow-up, 16,572 purchasing-session anchors have full coverage; 1,898 have a strictly later repeat within the horizon. 3,174 anchors also have equally long observed history. These are purchaser-only feasibility counts.

For 30-day follow-up, 1,019 purchasing-session anchors have full coverage; 192 have a strictly later repeat within the horizon. 0 anchors also have equally long observed history. These are purchaser-only feasibility counts.

## 1 — Customer behavior

A purchase event is a recorded item-level event, not an order. A purchasing session contains at least one purchase event; its purchase time is its first timestamped purchase. A purchasing day is a distinct UTC date per customer. A purchasing customer has at least one purchase event, including events with missing session IDs. Unknown customer IDs are excluded from customer metrics. Purchase-session distributions include a zero bucket for purchasers whose sessions are all missing. Counts of customer-days and customer-sessions sum per customer, rather than count purchase events.

### Customers

| metric | value |
| --- | --- |
| customers | 399,664 |
| purchasing_customers | 25,762 |
| non_purchasing_customers | 373,902 |
| multiple_purchasing_days | 2,492 |
| multiple_purchasing_sessions | 2,709 |
| purchasers_without_known_session | 0 |
| single_event_customers | 167,268 |
| purchase_events | 245,624 |
| customer_purchasing_days | 28,981 |
| customer_purchasing_sessions | 29,326 |

### Purchase session frequency

| purchasing_sessions | customers |
| --- | --- |
| 1 | 23053 |
| 2 | 2190 |
| 3+ | 519 |

### Purchase sessions distribution

| purchase_sessions | customers |
| --- | --- |
| 1 | 23053 |
| 2 | 2190 |
| 3 | 370 |
| 4 | 80 |
| 5 | 40 |
| 6 | 9 |
| 7 | 4 |
| 8 | 5 |
| 9 | 3 |
| 10 | 1 |
| 11 | 4 |
| 13 | 1 |
| 16 | 1 |
| 31 | 1 |

### Purchase days distribution

| purchase_days | customers |
| --- | --- |
| 1 | 23270 |
| 2 | 2033 |
| 3 | 326 |
| 4 | 77 |
| 5 | 30 |
| 6 | 8 |
| 7 | 6 |
| 8 | 5 |
| 9 | 3 |
| 10 | 2 |
| 11 | 1 |
| 21 | 1 |

## 2 — Session behavior

The raw session-ID audit precedes key selection. Observed key: `(user_id, user_session)`. Shared IDs trigger composite keys for both scenarios. Missing customer IDs remain in session metrics: under composite keys they form an unknown-user group; under global keys they retain the recorded session ID. Such events cannot be attributed to known customers. Session duration is last minus first observed timestamp, not active engagement time; single-event sessions have zero duration. Missing timestamps are excluded from duration bounds and calendar-day counts, and flagged. First/last October-day sessions are boundary-risk candidates, not proof of complete observation.

### Session identity

| raw_session_ids | shared_by_multiple_customers | ids_with_unknown_customer |
| --- | --- | --- |
| 873960 | 22 | 0 |

### Sessions

| metric | value |
| --- | --- |
| sessions | 873984 |
| with_view | 826170 |
| with_cart | 228147 |
| with_purchase | 29326 |
| with_remove_from_cart | 91973 |
| with_all_three | 20487 |
| purchase_without_view | 7127 |
| purchase_without_cart | 5135 |
| spanning_utc_days | 10785 |
| incomplete_timestamps | 0 |
| single_event_sessions | 521774 |
| multiple_purchase_events | 26395 |
| multiple_users_after_key_selection | 0 |
| outside_october | 0 |
| on_first_october_day | 29363 |
| on_last_october_day | 26708 |

### Event combinations

| has_view | has_cart | has_purchase | has_remove | sessions |
| --- | --- | --- | --- | --- |
| True | False | False | False | 624450 |
| True | True | False | False | 122382 |
| True | True | False | True | 47881 |
| False | True | False | False | 24580 |
| True | True | True | True | 15155 |
| True | False | False | True | 9258 |
| False | True | False | True | 9113 |
| False | False | False | True | 6994 |
| True | True | True | False | 5332 |
| False | False | True | False | 2746 |
| False | True | True | True | 2114 |
| False | True | True | False | 1590 |
| True | False | True | False | 931 |
| True | False | True | True | 781 |
| False | False | True | True | 677 |

### Events per session

| metric | value |
| --- | --- |
| observations | 873,984 |
| minimum | 1 |
| p25 | 1 |
| median | 1 |
| p75 | 4 |
| p90 | 9 |
| p95 | 20 |
| p99 | 58 |
| maximum | 1,488 |
| mean | 4.693045 |

### Products per session

| metric | value |
| --- | --- |
| observations | 873,984 |
| minimum | 1 |
| p25 | 1 |
| median | 1 |
| p75 | 2 |
| p90 | 6 |
| p95 | 13 |
| p99 | 33 |
| maximum | 1,073 |
| mean | 3.062539 |

### Duration seconds

| metric | value |
| --- | --- |
| observations | 873,984 |
| minimum | 0 |
| p25 | 0 |
| median | 0 |
| p75 | 91 |
| p90 | 920 |
| p95 | 2,601 |
| p99 | 50,540 |
| maximum | 2,636,582 |
| mean | 3,786.494458 |

## 3 — Funnel analysis

Both approaches are **session-level, across products**, not product-level funnels. Presence requires view, then the set {view, cart}, then the set {view, cart, purchase}, without ordering. Chronological stages require an observed view, a strictly later cart, and a strictly later purchase. The earliest view and earliest qualifying cart establish existence of a valid sequence; a wrong initial order can still be followed by a valid sequence. Equal timestamps never establish ordering. Tie-dependent counts show additional sessions accepted with non-strict ordering but excluded by the conservative strict policy. They indicate ambiguity, not confirmed conversions.

Rates are fractions in [0, 1]. Stage shares divide by **all eligible sessions**; view-to-cart and view-to-purchase divide by the approach's view sessions; cart-to-purchase divides by the approach's qualifying cart sessions. Drop-off is one minus the corresponding stage conversion; zero denominators yield missing rates. Raw records are the primary scenario.

Ordering anomalies count sessions with any timestamped purchase/cart before the first recorded view. The no-preceding-cart metric counts sessions where the earliest timestamped purchase has no strictly earlier cart (including ties). Events lacking timestamps cannot establish order. Timestamp ties count all same-time events within a selected session; exact identical source-row ties are also reported separately.

### Raw funnel

| metric | presence | chronological_strict |
| --- | --- | --- |
| all_sessions | 873,984 | 873,984 |
| view_sessions | 826,170 | 826,170 |
| cart_sessions | 190,750 | 178,355 |
| purchase_sessions | 20,487 | 19,410 |
| view_share_all_sessions | 0.945292 | 0.945292 |
| cart_share_all_sessions | 0.218253 | 0.204071 |
| purchase_share_all_sessions | 0.023441 | 0.022209 |
| view_to_cart | 0.230885 | 0.215882 |
| cart_to_purchase | 0.107402 | 0.108828 |
| view_to_purchase | 0.024798 | 0.023494 |
| view_to_cart_dropoff | 0.769115 | 0.784118 |
| cart_to_purchase_dropoff | 0.892598 | 0.891172 |

### Ordering anomalies

| purchase_before_first_view | cart_before_first_view | purchase_with_no_strictly_preceding_cart | tie_dependent_complete | tie_dependent_cart | views_without_valid_time |
| --- | --- | --- | --- | --- | --- |
| 468 | 38856 | 5344 | 7 | 92 | 0 |

### Timestamp ties

| tied_timestamp_groups | events_in_ties | sessions_with_ties | mixed_event_type_ties |
| --- | --- | --- | --- |
| 247474 | 708,960 | 81455 | 1787 |

### Identical event timestamp groups

| groups | raw_rows | excess_rows |
| --- | --- | --- |
| 205082 | 418,237 | 213,155 |

## 4 — Duplicate analysis

An exact duplicate matches all parsed source columns, including missing values. Excess rows count multiplicity minus one. Event-type duplicate percentages divide excess rows by raw rows of that type. Duplicate multiplicity tables count only groups with multiplicity > 1. Day and session distributions sum excess rows, with missing session rows reported separately. The session distribution uses explicit (user_id, user_session) pairs.

Scenario A preserves all records. Scenario B uses one row per exact group only in a temporary analytical relation. Neither source files nor a permanent deduplication policy are changed. Event and purchase-event counts and events-per-session are sensitive. Distinct customers, sessions, products, event-presence and existence-based strict funnels should be unchanged by exact duplicates; the measured side-by-side results below verify this. Timestamp-tie event counts can also be inflated by duplicates.

### Duplicate event types

| event_type | raw_events | excess_duplicate_rows | duplicate_percentage |
| --- | --- | --- | --- |
| view | 1,862,164 | 114 | 0.006122 |
| cart | 1,232,385 | 28,167 | 2.285568 |
| remove_from_cart | 762,110 | 184,531 | 24.213171 |
| purchase | 245,624 | 343 | 0.139644 |

### Duplicate multiplicity

| multiplicity | groups | excess_duplicate_rows |
| --- | --- | --- |
| 2 | 200356 | 200,356 |
| 3 | 3159 | 6,318 |
| 4 | 902 | 2,706 |
| 5 | 242 | 968 |
| 6 | 138 | 690 |
| 7 | 93 | 558 |
| 8 | 83 | 581 |
| 9 | 54 | 432 |
| 10 | 30 | 270 |
| 11 | 11 | 110 |
| 12 | 9 | 99 |
| 13 | 3 | 36 |
| 14 | 1 | 13 |
| 19 | 1 | 18 |

### Duplicate session summary

| customer_session_pairs | pairs_with_duplicates | maximum_excess_rows | excess_rows |
| --- | --- | --- | --- |
| 873984 | 58669 | 637 | 213,092 |

### Duplicate session distribution

| excess_rows | customer_session_pairs |
| --- | --- |
| 0 | 815315 |
| 1 | 30842 |
| 2 | 8217 |
| 3 | 4800 |
| 4 | 3219 |
| 5 | 2359 |
| 6 | 1704 |
| 7 | 1230 |
| 8 | 979 |
| 9 | 769 |
| 10 | 681 |
| 11 | 558 |
| 12 | 420 |
| 13 | 329 |
| 14 | 293 |
| 15 | 222 |
| 16 | 220 |
| 17 | 190 |
| 18 | 167 |
| 19 | 137 |
| 20 | 105 |
| 21 | 110 |
| 22 | 91 |
| 23 | 96 |
| 24 | 69 |
| 25 | 67 |
| 26 | 60 |
| 27 | 53 |
| 28 | 46 |
| 29 | 43 |
| 30 | 49 |
| 31 | 33 |
| 32 | 26 |
| 33 | 18 |
| 34 | 28 |
| 35 | 32 |
| 36 | 15 |
| 37 | 9 |
| 38 | 18 |
| 39 | 14 |
| 40 | 17 |
| 41 | 19 |
| 42 | 19 |
| 43 | 12 |
| 44 | 16 |
| 45 | 18 |
| 46 | 15 |
| 47 | 7 |
| 48 | 8 |
| 49 | 8 |
| 50 | 9 |
| 51 | 6 |
| 52 | 9 |
| 53 | 8 |
| 54 | 5 |
| 55 | 8 |
| 56 | 4 |
| 57 | 6 |
| 58 | 13 |
| 59 | 5 |
| 60 | 2 |
| 61 | 4 |
| 62 | 7 |
| 63 | 2 |
| 64 | 3 |
| 65 | 3 |
| 66 | 3 |
| 67 | 3 |
| 68 | 3 |
| 69 | 6 |
| 70 | 4 |
| 71 | 2 |
| 72 | 3 |
| 73 | 2 |
| 74 | 2 |
| 75 | 5 |
| 76 | 4 |
| 77 | 2 |
| 78 | 1 |
| 79 | 1 |
| 80 | 2 |
| 81 | 1 |
| 82 | 3 |
| 83 | 1 |
| 84 | 3 |
| 85 | 2 |
| 86 | 2 |
| 87 | 1 |
| 88 | 2 |
| 89 | 2 |
| 90 | 1 |
| 92 | 1 |
| 93 | 1 |
| 94 | 1 |
| 96 | 2 |
| 97 | 2 |
| 100 | 2 |
| 103 | 1 |
| 107 | 1 |
| 108 | 1 |
| 109 | 2 |
| 110 | 2 |
| 111 | 1 |
| 112 | 1 |
| 115 | 1 |
| 121 | 1 |
| 123 | 1 |
| 124 | 1 |
| 125 | 1 |
| 133 | 1 |
| 134 | 1 |
| 135 | 1 |
| 137 | 1 |
| 140 | 1 |
| 141 | 1 |
| 142 | 1 |
| 143 | 2 |
| 144 | 2 |
| 146 | 1 |
| 150 | 1 |
| 157 | 1 |
| 161 | 1 |
| 166 | 1 |
| 169 | 1 |
| 176 | 1 |
| 178 | 1 |
| 184 | 1 |
| 187 | 1 |
| 192 | 1 |
| 198 | 1 |
| 206 | 1 |
| 219 | 1 |
| 226 | 1 |
| 261 | 1 |
| 281 | 1 |
| 291 | 1 |
| 316 | 1 |
| 329 | 1 |
| 355 | 1 |
| 358 | 1 |
| 637 | 1 |

### Duplicate missing sessions

| excess_rows_with_missing_session |
| --- |
| 63 |

### Duplicate days

| day_utc | excess_duplicate_rows | duplicate_groups |
| --- | --- | --- |
| 2019-10-01 | 7,487 | 7201 |
| 2019-10-02 | 10,499 | 10265 |
| 2019-10-03 | 6,197 | 5862 |
| 2019-10-04 | 5,655 | 5480 |
| 2019-10-05 | 5,595 | 5389 |
| 2019-10-06 | 11,808 | 11511 |
| 2019-10-07 | 10,362 | 10199 |
| 2019-10-08 | 9,343 | 8786 |
| 2019-10-09 | 7,635 | 7308 |
| 2019-10-10 | 7,137 | 6787 |
| 2019-10-11 | 6,258 | 6031 |
| 2019-10-12 | 5,795 | 5538 |
| 2019-10-13 | 6,050 | 5818 |
| 2019-10-14 | 5,688 | 5513 |
| 2019-10-15 | 5,852 | 5728 |
| 2019-10-16 | 6,531 | 6300 |
| 2019-10-17 | 6,505 | 6238 |
| 2019-10-18 | 5,970 | 5695 |
| 2019-10-19 | 5,968 | 5625 |
| 2019-10-20 | 6,467 | 6210 |
| 2019-10-21 | 6,912 | 6594 |
| 2019-10-22 | 6,893 | 6622 |
| 2019-10-23 | 7,289 | 6614 |
| 2019-10-24 | 6,690 | 6462 |
| 2019-10-25 | 5,340 | 5252 |
| 2019-10-26 | 5,908 | 5525 |
| 2019-10-27 | 6,779 | 6669 |
| 2019-10-28 | 6,311 | 6101 |
| 2019-10-29 | 6,467 | 6292 |
| 2019-10-30 | 5,820 | 5666 |
| 2019-10-31 | 5,944 | 5801 |

### Scenario impact

| metric | raw | deduplicated | deduplicated_minus_raw |
| --- | --- | --- | --- |
| events | 4,102,283 | 3,889,128 | -213,155 |
| customers | 399,664 | 399,664 | 0 |
| raw_unique_session_ids | 873,960 | 873,960 | 0 |
| analytical_sessions | 873,984 | 873,984 | 0 |
| purchase_events | 245,624 | 245,281 | -343 |
| presence_view_sessions | 826,170 | 826,170 | 0 |
| presence_cart_sessions | 190,750 | 190,750 | 0 |
| presence_purchase_sessions | 20,487 | 20,487 | 0 |
| presence_view_to_purchase | 0.024798 | 0.024798 | 0 |
| chronological_strict_view_sessions | 826,170 | 826,170 | 0 |
| chronological_strict_cart_sessions | 178,355 | 178,355 | 0 |
| chronological_strict_purchase_sessions | 19,410 | 19,410 | 0 |
| chronological_strict_view_to_purchase | 0.023494 | 0.023494 | 0 |

### Raw counts

| events | customers | raw_unique_session_ids | analytical_sessions | purchase_events |
| --- | --- | --- | --- | --- |
| 4102283 | 399664 | 873960 | 873984 | 245624 |

### Deduplicated counts

| events | customers | raw_unique_session_ids | analytical_sessions | purchase_events |
| --- | --- | --- | --- | --- |
| 3889128 | 399664 | 873960 | 873984 | 245281 |

### Raw funnel

| metric | presence | chronological_strict |
| --- | --- | --- |
| all_sessions | 873,984 | 873,984 |
| view_sessions | 826,170 | 826,170 |
| cart_sessions | 190,750 | 178,355 |
| purchase_sessions | 20,487 | 19,410 |
| view_share_all_sessions | 0.945292 | 0.945292 |
| cart_share_all_sessions | 0.218253 | 0.204071 |
| purchase_share_all_sessions | 0.023441 | 0.022209 |
| view_to_cart | 0.230885 | 0.215882 |
| cart_to_purchase | 0.107402 | 0.108828 |
| view_to_purchase | 0.024798 | 0.023494 |
| view_to_cart_dropoff | 0.769115 | 0.784118 |
| cart_to_purchase_dropoff | 0.892598 | 0.891172 |

### Deduplicated funnel

| metric | presence | chronological_strict |
| --- | --- | --- |
| all_sessions | 873,984 | 873,984 |
| view_sessions | 826,170 | 826,170 |
| cart_sessions | 190,750 | 178,355 |
| purchase_sessions | 20,487 | 19,410 |
| view_share_all_sessions | 0.945292 | 0.945292 |
| cart_share_all_sessions | 0.218253 | 0.204071 |
| purchase_share_all_sessions | 0.023441 | 0.022209 |
| view_to_cart | 0.230885 | 0.215882 |
| cart_to_purchase | 0.107402 | 0.108828 |
| view_to_purchase | 0.024798 | 0.023494 |
| view_to_cart_dropoff | 0.769115 | 0.784118 |
| cart_to_purchase_dropoff | 0.892598 | 0.891172 |

## 5 — Purchase frequency and prediction horizons

Intervals are fractional elapsed days between consecutive known customer purchasing sessions, ordered by first purchase time. Repeated purchase events within a session do not create intervals. Missing session/customer IDs and entirely untimestamped purchase sessions cannot contribute. Tied session starts contribute zero-day intervals; their internal order is unknowable. Percentiles are continuous; the observations column counts nonmissing intervals, not customers. Last observed purchasing sessions are right-censored, not evidence that a customer never returns.

Horizon feasibility uses each timestamped purchasing session as an exploratory anchor. Full follow-up requires anchor + horizon ≤ the last observed event; a repeat must be a distinct session at a strictly later first-purchase time within the horizon. The next strictly later start is used so tied starts cannot hide a later repeat. Equal-history-and-follow-up counts additionally require anchor − horizon ≥ the first observed event. These bounds assume continuous source coverage, not continuous customer activity. Anchors overlap and come only from observed purchasers: these are feasibility counts, not final labels or estimates for all customers. Daily customer-session counts can count a session on more than one date if it purchases across midnight.

### Purchase intervals days

| metric | value |
| --- | --- |
| observations | 3,564 |
| minimum | 0.000984 |
| p25 | 1.405000 |
| median | 6.210567 |
| p75 | 12.400179 |
| p90 | 18.516104 |
| p95 | 21.864637 |
| p99 | 27.121176 |
| maximum | 30.173333 |
| mean | 7.823962 |

### Interval quality

| tied_purchase_session_starts | right_censored_last_sessions |
| --- | --- |
| 0 | 25762 |

### Daily purchase activity

| day_utc | purchase_events | purchasing_customers | customer_purchasing_sessions |
| --- | --- | --- | --- |
| 2019-10-01 | 8476 | 1001 | 1019 |
| 2019-10-02 | 9100 | 1045 | 1068 |
| 2019-10-03 | 8865 | 1048 | 1058 |
| 2019-10-04 | 7562 | 892 | 911 |
| 2019-10-05 | 5940 | 708 | 724 |
| 2019-10-06 | 7265 | 834 | 849 |
| 2019-10-07 | 9376 | 1116 | 1133 |
| 2019-10-08 | 8604 | 1038 | 1051 |
| 2019-10-09 | 8464 | 1057 | 1073 |
| 2019-10-10 | 8117 | 982 | 994 |
| 2019-10-11 | 6922 | 875 | 887 |
| 2019-10-12 | 6431 | 780 | 796 |
| 2019-10-13 | 7088 | 817 | 829 |
| 2019-10-14 | 8004 | 1045 | 1065 |
| 2019-10-15 | 8299 | 988 | 1007 |
| 2019-10-16 | 9096 | 1089 | 1108 |
| 2019-10-17 | 9236 | 1060 | 1073 |
| 2019-10-18 | 7920 | 923 | 939 |
| 2019-10-19 | 6064 | 687 | 694 |
| 2019-10-20 | 6836 | 799 | 813 |
| 2019-10-21 | 8872 | 1043 | 1063 |
| 2019-10-22 | 8643 | 1012 | 1032 |
| 2019-10-23 | 8714 | 1030 | 1051 |
| 2019-10-24 | 8779 | 977 | 996 |
| 2019-10-25 | 7024 | 851 | 861 |
| 2019-10-26 | 5295 | 617 | 631 |
| 2019-10-27 | 7816 | 911 | 927 |
| 2019-10-28 | 8366 | 997 | 1019 |
| 2019-10-29 | 8472 | 929 | 944 |
| 2019-10-30 | 7935 | 896 | 912 |
| 2019-10-31 | 8043 | 934 | 952 |

### Horizon feasibility

| metric | 7 | 14 | 30 |
| --- | --- | --- | --- |
| first_event | 2019-10-01 00:00:00+00:00 | 2019-10-01 00:00:00+00:00 | 2019-10-01 00:00:00+00:00 |
| last_event | 2019-10-31 23:59:54+00:00 | 2019-10-31 23:59:54+00:00 | 2019-10-31 23:59:54+00:00 |
| known_purchase_session_anchors | 29326 | 29326 | 29326 |
| full_followup_anchors | 23127 | 16572 | 1019 |
| full_followup_anchors_with_repeat | 1646 | 1898 | 192 |
| customers_with_full_followup | 20759 | 15267 | 1001 |
| anchors_with_equal_history_and_followup | 16380 | 3174 | 0 |

## 6 — Data quality and limitations

Source absence is not necessarily behavioral absence: sessions and prior customer history may start before October, and future purchases may occur after it. No session is artificially split at midnight. Outside-October events are retained and counted, not filtered. First and last observed timestamps bound this file only; completeness and timestamp precision need upstream confirmation. No secondary order is invented for equal event times. Missing timestamps remain in presence counts, but cannot advance chronological stages. Empty CSV fields are missing; whitespace or literal 'NULL' strings remain source values under the Phase 1.1 convention.

Missing brand/category metadata is retained and prevents reliable segmentation without a later documented policy. Unknown sessions/customers prevent attribution. Shared session IDs may reflect instrumentation issues; composite keys separate known customers but cannot resolve identity errors. Exact duplicates may reflect ingestion retries or genuine repeated actions; their cause remains unknown. Purchase events do not supply order IDs, so order count, basket boundaries, and true repeat-order frequency cannot be inferred directly.

### Quality

| metric | value |
| --- | --- |
| events | 4102283 |
| unique_customers | 399664 |
| raw_unique_session_ids | 873960 |
| excluded_session_events | 637 |
| excluded_customer_events | 0 |
| missing_timestamps | 0 |
| first_event | 2019-10-01 00:00:00+00:00 |
| last_event | 2019-10-31 23:59:54+00:00 |
| outside_october | 0 |

### Missing values

| column_name | missing_values |
| --- | --- |
| event_time | 0 |
| event_type | 0 |
| product_id | 0 |
| category_id | 0 |
| category_code | 4034806 |
| brand | 1659261 |
| price | 0 |
| user_id | 0 |
| user_session | 637 |

## 7 — Recommendations

Use the measured 7/14/30-day feasibility counts to choose an exploratory horizon, balancing repeat support and complete follow-up. Seven and fourteen days are candidates for further investigation; one October file cannot support both 30-day feature history and 30-day outcome observation. Add later months before final horizon selection, labeling, or chronological validation. Repeat activity supports investigating a customer-level task but does not establish model usefulness or an adequate positive rate across all customers.

Confirm session-ID generation, UTC precision, source completeness, order identifiers, and duplicate provenance with dataset documentation. Retain both duplicate scenarios until an explicit policy is justified. Next, define observation windows and feature availability, reserve future time for validation, and compare simple baselines only after labels and leakage controls are agreed. No model or infrastructure is introduced in this phase.

## Reproduction

From the repository root after installing `.[dev]`:

```bash
source .venv/bin/activate
python scripts/explore_behavior.py --input "data/raw/2019-Oct.csv" \
  --output data/processed/phase-1.2 \
  --report docs/reports/phase-1.2-october-2019.md
pytest
ruff check .
ruff format --check .
```

All aggregate tables are exported as CSV, including empty tables with headers. CSV outputs are ignored by Git. The Markdown report records the source path and definitions. Rerunning replaces generated outputs. No customer-level identifiers are exported. SQL runs over all rows in DuckDB with a 2 GB working-memory limit, two threads, and temporary disk spill space; only aggregated results enter Pandas.
