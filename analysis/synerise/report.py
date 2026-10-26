"""Render measured aggregate research results; never estimates missing measurements."""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
r = json.loads((ROOT / "results.json").read_text())
s = json.loads((ROOT / "supplement.json").read_text())
d = json.loads((ROOT / "download-manifest.json").read_text())
EVENTS = ("page_visit", "search_query", "add_to_cart", "remove_from_cart", "product_buy")
REFERENCE = dict(zip(EVENTS, (150713186, 9571258, 5235882, 1697891, 1682296), strict=True))


def table(headers, rows):
    def value(v):
        if isinstance(v, int):
            return f"{v:,}"
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
                *["| " + " | ".join(value(v) for v in row) + " |" for row in rows],
            ]
        )
        + "\n"
    )


profiles = {n: r[n + "_profile"][0] for n in EVENTS}
counts = table(
    ["Event", "Published", "Measured", "Difference", "Exact clients", "Excess duplicates"],
    [
        (
            n,
            REFERENCE[n],
            profiles[n]["events"],
            profiles[n]["events"] - REFERENCE[n],
            profiles[n]["clients"],
            r[n + "_duplicates"][0]["excess_rows"],
        )
        for n in EVENTS
    ],
)
snapshot_table = table(
    ["Snapshot (source clock)", "Eligible", "Positive", "Negative", "Rate", "Label end"],
    [
        (
            x["snapshot"],
            x["eligible"],
            x["positives"],
            x["negatives"],
            f"{x['positive_rate']:.2%}",
            x["label_end_exclusive"],
        )
        for x in r["snapshots"]
        if x["definition"] == "A_event"
    ],
)
purchase_table = table(
    [
        "Definition",
        "Purchasers",
        "Repeat purchasers",
        "Median signals",
        "Median gap days",
        "Zero gaps",
    ],
    [
        (
            x["definition"],
            x["purchasers"],
            x["repeat_purchasers"],
            x["median"],
            x["median_gap_days"],
            x["zero_gaps"],
        )
        for x in r["purchases"]
    ],
)
funnel_table = table(
    [
        "Window",
        "Page",
        "Page→cart",
        "Page→cart→buy",
        "Page→search",
        "→cart",
        "→buy",
        "Same-SKU cart→buy clients",
    ],
    [
        (
            "full history" if n == -1 else f"{n} days",
            *[
                r[f"funnel_{n}"][0][k]
                for k in (
                    "page_customers",
                    "page_cart",
                    "page_cart_buy",
                    "page_search",
                    "page_search_cart",
                    "page_search_cart_buy",
                    "sku_cart_buy_customers",
                )
            ],
        )
        for n in (-1, 1, 7, 30)
    ],
)
p = r["customer_funnel"][0]
presence = table(["Presence stage", "Clients"], [(k, v) for k, v in p.items()])
h = r["customer_history"][0]
t = r["purchase_ties"][0]
f = s["features"][0]
product = r["product_metadata"][0]
feature_table = table(
    ["30-day feature", "Zero / missing activity clients", "Fraction of eligible"],
    [
        (name, f[key], f"{f[key] / f['eligible']:.2%}")
        for name, key in (
            ("Any activity", "zero_activity_30d"),
            ("Page visits", "zero_page_visits_30d"),
            ("Searches", "zero_searches_30d"),
            ("Cart additions", "zero_cart_adds_30d"),
            ("Cart removals", "zero_cart_removals_30d"),
            ("Purchases", "zero_purchases_30d"),
        )
    ],
)
monthly = table(
    ["Month", "Purchase events", "Purchasing clients"],
    [(x["month"], x["events"], x["clients"]) for x in r["product_buy_monthly"]],
)
source_dates = table(
    ["Event", "First timestamp", "Last timestamp", "Distinct SKU / URL"],
    [
        (
            n,
            profiles[n]["first_ts"],
            profiles[n]["last_ts"],
            profiles[n].get("distinct_values", "not applicable"),
        )
        for n in EVENTS
    ],
)
schema = []
for name in (*EVENTS, "product_properties"):
    for col in r[name + "_schema"]:
        schema.append(
            (
                name,
                col["column_name"],
                col["column_type"],
                col["null"],
                r[name + "_nulls"][0][col["column_name"] + "_nulls"],
            )
        )
(ROOT / "schema.md").write_text(
    "# Verified source schema\n\n"
    + table(["File", "Column", "DuckDB type", "Nullable schema", "Observed nulls"], schema)
    + "\nThe name/query fields are VARCHAR vector encodings, not nested arrays. "
    "All timestamps are VARCHAR, parsed as timezone-naive TIMESTAMP.\n"
)
measured_total = sum(x["events"] for x in profiles.values())
assert all(x["full_followup"] for x in r["snapshots"])
assert all(x["positives"] + x["negatives"] == x["eligible"] for x in r["snapshots"])
assert datetime.fromisoformat(f["maximum_historical_timestamp"]) < datetime.fromisoformat(
    f["snapshot"]
)

for event in EVENTS:
    assert r[event + "_nulls"][0]["rows"] == profiles[event]["events"]
    assert sum(x["events"] for x in r[event + "_daily"]) == profiles[event]["events"]
    assert sum(x["events"] for x in r[event + "_monthly"]) == profiles[event]["events"]
    duplicate = r[event + "_duplicates"][0]
    assert duplicate["distinct_rows"] + duplicate["excess_rows"] == profiles[event]["events"]
for days in (-1, 1, 7, 30):
    funnel = r[f"funnel_{days}"][0]
    assert funnel["page_customers"] == profiles["page_visit"]["clients"]
    assert funnel["page_cart_buy"] <= funnel["page_cart"] <= funnel["page_customers"]
    assert funnel["page_search_cart_buy"] <= funnel["page_search_cart"] <= funnel["page_search"]

for date in {x["snapshot"] for x in r["snapshots"]}:
    variants = [x for x in r["snapshots"] if x["snapshot"] == date]
    assert len({(x["eligible"], x["positives"], x["negatives"]) for x in variants}) == 1
report = f"""# Phase 3.3 — Synerise RecSys 2025 feasibility assessment

Measured 21 October 2026. **CONDITIONAL GO for the two analytical tasks**, provided
we accept a behavioral client funnel without actual sessions/checkout/order IDs,
retain the event-based purchase target, and resolve source-version/timezone and
NonCommercial-use requirements before adopting it. This is evidence to consider
replacement, not approval to migrate. Existing REES46 remains unchanged.

## Source, licensing and access

Used the **original** six-file Synerise archive linked by the
[official dataset page](https://recsys.synerise.com/data-set), without competition
client filtering or input/target preprocessing. The public download needed no
account. Downloaded {d["archive_bytes"]:,} bytes; extracted Parquet totals
{d["selected_bytes"]:,} bytes. SHA-256: `{d["archive_sha256"]}`.
[Inventory and per-file hashes](../../analysis/synerise/download-manifest.json).
The server reported last-modified 12 November 2025; download completed in about
75 seconds. No interrupted-transfer resume test was needed.

Attribution: Universal Behavioral Modeling Dataset © 2025 Synerise SA,
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), as identified by
[the organizer's notice](https://recsys.synerise.com/summary). Give credit, link the
license, and identify analytical transformations; do not imply endorsement.
Noncommercial portfolio publication must respect the NonCommercial restriction;
public GitHub visibility does not by itself establish compliant use. Commercial,
sponsored or paid reuse requires a separate permission assessment. The organizer's
code MIT license is distinct from its data license. Only aggregate results are
included here; source records remain ignored local files.

## Verified schemas and counts

{counts}
Total measured events: **{measured_total:,}**. All five counts exceed the published
reference. These are complete scans, not estimates or sampled clients. The public
URL currently supplies a different-sized corpus than the reference table. A later
release or different filtering is plausible, but **the exact cause is unconfirmed**;
no rows were removed to force agreement. Confirm the release with the publisher
before claiming equivalence to published competition results. Hash-pinned results
remain reproducible for this actual archive.

See [full measured schema/null table](../../analysis/synerise/schema.md). Event
identifiers are BIGINT; timestamps are VARCHAR. Purchase/cart records have SKU;
page records have URL; searches have a VARCHAR query-vector encoding. Properties
have SKU, category, price, name, all nullable by schema. Every source column has
**zero observed nulls** and every event timestamp parses successfully. All parsed
times have whole-second precision. One page row has a nonpositive client ID; none
of the other event types do. We retain it and flag it, not infer its meaning.
Approximate distinct-client diagnostics are also recorded, but diverge noticeably
from exact counts; conclusions use exact values.

{source_dates}
No source timezone is established by the inspected documentation. All dates and
cutoffs in this report are **source-clock times**, not verified UTC. All five event
types have records on every one of the 169 calendar dates between
their endpoints; this does not prove uninterrupted within-day tracking. Ordering is
valid within the supplied clock, but exact UTC deployment alignment requires
confirmation. Approximately 96.7% of each event type's seconds are multiples of
five, so timestamp coarsening/ties are material. We do not invent subsecond order.

Exact duplicate rates are excess rows / raw rows, computed from all source columns;
raw multiplicities remain intact. Purchase excess duplicates are
{r["product_buy_duplicates"][0]["excess_rows"]:,}
({r["product_buy_duplicates"][0]["excess_rows"] / profiles["product_buy"]["events"]:.2%}).
Page excess duplicates are {r["page_visit_duplicates"][0]["excess_rows"]:,}
({r["page_visit_duplicates"][0]["excess_rows"] / profiles["page_visit"]["events"]:.2%}).
They may reflect repeated signals, instrumentation or preprocessing; cause is unknown.

## Product properties and encoded fields

Properties contain {product["rows"]:,} rows and {product["skus"]:,} distinct SKUs,
with no duplicate SKU keys or exact duplicate rows; {product["categories"]:,}
categories and price buckets {product["minimum_price_bucket"]}–{product["maximum_price_bucket"]}.
Every observed buy/add/remove SKU matches properties. Full property joins therefore
avoid unmatched records in this version; never assume this for another release.

All measured query/name vectors have 16 extracted integers, stored as
whitespace-separated strings. The dataset webpage describes 20-dimensional queries,
while the repository describes 16-code quantization: actual files support the
latter. They are not readable query text or ordinary continuous semantic vectors.
Price is an anonymized bucket, **not money or revenue**. Static properties have no
valid-from timestamp: historical feature availability is not verifiable without
an explicit immutability assumption or a temporal source. URL IDs have no supplied
SKU/page-type mapping; no product-detail views can be reconstructed defensibly.

## Persistent client identity and history

Exact observed clients overall: **{h["customers"]:,}**. Clients active on multiple
days: {h["multi_day_customers"]:,}; across multiple months:
{h["multi_month_customers"]:,}. Purchasing clients: {h["purchasing_customers"]:,};
clients purchasing on more than one date: {h["multi_purchase_day_customers"]:,}.

Median / p90 events per client: {h["median_events"]} / {h["p90_events"]};
maximum {h["maximum_events"]:,}. Median / p90 active days:
{h["median_active_days"]} / {h["p90_active_days"]}. Median / p90 first-to-last
observed span: {h["median_span_days"]:.2f} / {h["p90_span_days"]:.2f} days.
Median recency from dataset end: {h["median_last_activity_recency_days"]:.2f} days.
These are observation spans, not account tenure or complete customer histories.

The same typed client IDs occur across event types; measured overlaps with purchase
clients are in `supplement.json`. This supports longitudinal joins. It does not
prove a person-level identity, logged-in status, cross-device completeness or
absence of identity resets. The large page population is much broader than the
purchaser cohort. No anonymous/logged-in distinction is supplied.

## Purchase interpretation and repeat signals

{purchase_table}

There are {t["occasions"]:,} distinct client/timestamp occasions;
{t["multi_event_occasions"]:,} have multiple rows and
{t["multi_sku_occasions"]:,} contain multiple SKUs. Maximum rows at one occasion:
{t["maximum_events"]:,}. This is direct evidence that row frequency is not order
frequency. Same-time multi-SKU activity is compatible with basket transactions,
but **no order identifier exists**. Same-day and same-time grouping are sensitivity
heuristics, never reconstructed true orders.

A retains all item-level product_buy signals. B collapses exact customer/time;
C collapses customer/calendar date. Zero-day gaps in A include ties/duplicates.
B removes same-time multiplicity, and C removes same-day multiplicity. Positive
inter-signal gaps within one hour and p90 gaps are in the full results. Repeat
client/SKU and client/category pair counts are also measured there, requiring
more than one distinct purchase timestamp. Refund, cancellation, quantity and
completed-order status cannot be established from these columns.

{monthly}

## Behavioral funnels

The business interpretation is observed page activity → cart action → purchase
signal, with **search optional**. Do not infer view_item, checkout, shipping,
payment or actual sessions. Full-period cumulative event presence:

{presence}
Strictly chronological, bounded from initial page to conversion:

{funnel_table}
All counts are unique clients per cumulative stage; repeat events cannot inflate
converted clients. Timestamps must strictly increase. A later valid chain can
qualify even if earlier records are out of order. The full-history chain is not
a session; 1/7/30-day alternatives constrain attribution. These limits are
exploratory, not an established business conversion window.

Same-SKU cart-to-buy counts are separate product-specific evidence, not a SKU
page funnel. Page/search cannot be assigned a product. Equal-time cross-event
pairs are measured in `supplement.json` and excluded as ordering evidence.
Missing cart/search records are not repaired from a purchase. Mandatory-search
funnels exclude legitimate nonsearch journeys and must not be the sole KPI.

For the 30-day no-search funnel, page→cart drop-off is
{1 - r["funnel_30"][0]["page_cart"] / r["funnel_30"][0]["page_customers"]:.2%};
qualifying cart→purchase drop-off is
{1 - r["funnel_30"][0]["page_cart_buy"] / r["funnel_30"][0]["page_cart"]:.2%}.
There is no natural session identifier. No inactivity-based session was generated.

## Chronological 14-day ML feasibility

{snapshot_table}
Dates are derived from the measured range: four latest month starts at least two
month boundaries after the first month and with 14 days before the last event.
Use the first two for training, third for validation, fourth for untouched holdout.
Every eligible client has a purchase strictly before its cutoff; history uses
`timestamp < t`, and labels alone use `[t,t+14 days)`. Training labels end before
validation, and validation labels end before holdout. No features/models were built.

A, B and C have **identical binary eligibility and labels at these midnight
cutoffs**, verified automatically. Grouping at the same timestamp/day cannot move
a signal across these day-aligned boundaries. That agreement does not validate
order semantics; frequency features and repeat counts above differ substantially.

Observed history before these snapshots is approximately 39, 70, 100 and 131 days,
respectively; it is a maximum dataset lookback, not per-customer tenure.

Ever-purchaser cohorts are nested. Independent first-purchase queries confirmed
all six pairwise overlaps (stored in supplement.json). Shared-client counts equal the earlier
snapshot's eligible count; repeated clients are expected, not independent samples.
This is returning-customer evaluation, not new-customer generalization. Positive
rates vary by date; preserve chronological holdout and compare prevalence baselines
later. No model quality, feature importance or predictive lift is claimed.

History is left-censored at the source start; late outcomes are right-censored.
Observed bounds and daily continuity are necessary but cannot prove complete
logging. All daily/monthly event and unique-client aggregates are retained. Require
upstream timezone/coverage confirmation before treating negative labels as fully
observed business outcomes.

## Historical feature availability and sparsity

At {f["snapshot"]}, {f["eligible"]:,} eligible prior purchasers:

{feature_table}

Maximum timestamp contributing to this historical coverage:
{f["maximum_historical_timestamp"]}, strictly before cutoff. No future events or
competition target arrays enter it. Missing activity yields zeros rather than
customer exclusion. Median 30-day active days and distinct cart SKUs are both zero.

Recency, 7/30/60-day counts, active days, cart/remove/search/page frequencies,
SKU diversity, repeated SKU activity and recent/earlier activity ratios are
computable from cutoff-filtered raw events. Occasion/day frequency variants should
accompany event-frequency features. The first snapshot has only about 39 days of
observed history, so a 60-day
feature would be partial; use a common 30-day lookback or explicit coverage flags.
Category diversity and price-bucket preferences need an explicit assumption that
the undated static attributes were known at cutoff.
Historical cart-to-buy rates must count only purchases before cutoff, never use
future labels to finish historical carts. Trends need equal-length disjoint
historical windows and guarded zero denominators. Predictive usefulness remains
untested. No actual revenue/order-count feature is supported.

## Organizer target and temporal implementation

Inspected official repository revision
`e91c1a62f84611151a399ce157e6031a4a73618f`, including
[split_data.py](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/data_utils/split_data.py),
[target calculators](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/training_pipeline/target_calculators.py)
and
[task construction](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/training_pipeline/task_constructor.py).

The splitter uses a 14-day constant. Relative to final purchase time, it computes
training-target start as end minus 27 days, reset to midnight, then validation
start 14 days later. Input is strictly before training start; training target is
half-open up to validation start; validation includes the final endpoint. A
non-full final day means its last evaluation interval is not automatically 14 full
days. We use explicitly full half-open horizons instead.

Churn filtering loads externally supplied `active_clients.npy`; documentation
identifies these as relevant clients with prior purchases. The code itself does
not recompute that eligibility at each rolling cutoff. Churn is 1 for no target
purchase, inverse of our repeat-event target within the same universe/window.
Propensity is multilabel purchase presence for selected SKU/category/bucket values,
not unrestricted repeat purchasing. The splitter creates purchase-only targets,
so emptiness in the target calculator means no purchase there, not no activity.
No organizer training code was executed. Its full-file Pandas loading, fixed
selected client universe and embedding-model protocol are not reused. Reuse the
conceptual separation and cross-check label logic, not its whole benchmark.

## Resources and future compatibility

Preflight: about 1.4 TiB free disk and 128 GiB RAM. Archive + extracted Parquet
requires about 4.35 GiB; product properties are included. The page file alone is
2,010,901,793 bytes. It is much larger than the other event sources and dominates
client aggregation, duplicate grouping and temporal page joins.

DuckDB ran with 2 GB working memory, two threads and an 80 GB spill cap. The first
unpartitioned page-duplicate aggregation hit the cap and failed without changing
source data; a 32-way client partition strategy completed it. Customer histories
also use 32 partitions and funnels 16. This is important implementation evidence:
a naive whole-corpus groupby does not fit the project's existing budget. The cap
is a database working-memory setting, not a measured whole-process peak.
Per-query elapsed times and SQL are preserved; cached/resumed work is identified
by matching prior executed query text, so the final duration is not a clean
from-scratch end-to-end benchmark. CPU/IO caches and multiple local research
processes also affect timings. No ClickHouse load benchmark was performed.

For future storage, preserve five typed raw source tables and undated properties;
expose a normalized analytical UNION ALL with event kind, original client/time,
SKU where present, URL only for pages and quantized query only for searches.
Keep original timestamp text until timezone is resolved. A raw normalized projection
with three 8-byte identifiers/time fields is already about 5.4 GB uncompressed
before strings/vectors/null/provenance overhead. Actual compressed ClickHouse size
is **unmeasured**; reserve 10–20 GB as a planning allowance, plus temporary staging
and reconciliation space, rather than asserting a compression ratio.

At the earlier REES46 transfer sample of ~320k rows/s, a purely linear scale for
this corpus would be roughly {measured_total / 320277 / 60:.1f} minutes of transfer.
That is an extrapolation, not a runtime promise: schema, sorting, disk, parsing and
reconciliation differ. Full pipeline runtime is unknown. Daily partitions and
bounded-memory batches would be practical investigation candidates after approval.
Do not use price buckets as Decimal revenue or force page URL into SKU. No database
migration, production schemas, dbt models or Docker operations were performed.

## Comparison and recommendation

REES46 has 20.69M validated events, five months, existing four customer snapshots
and measured baselines; its view event has SKU but no order ID. Synerise offers
much more real recorded activity, search/URL signals and substantially more
purchasing clients, but no documented product-page mapping or real sessions.
Both require item-event versus order caution. This corpus cannot support the full
GA4 checkout funnel, but it can support the requested meaningful behavioral funnel.

The synthetic generator had 303 purchasing login IDs, hand-written return behavior
and ~51–56% 14-day rates; it was useful for engineering, not real-customer model
validity. Synerise supplies measured real-world longitudinal purchase behavior,
with materially larger label cohorts. Public GA4 sample access remains a separate
INCONCLUSIVE assessment. Size alone is not the reason for this recommendation.

**CONDITIONAL GO:** retain raw multiplicity and event-target semantics; accept
purchase occasions as sensitivity heuristics, source-clock ordering until timezone
confirmation, optional search and missing checkout/session/page-type information;
pin the larger current release and resolve its count discrepancy; comply with
NonCommercial use and attribution. These restrictions permit research on both
required tasks. Do not call labels true repeat orders or claim customer identity
completeness. Review these conditions before replacing REES46. If exact order-level
outcomes or product-view/checkout stages are mandatory, this source does not meet
those stronger requirements.

## Reproducibility and outstanding limits

[Research instructions](../../analysis/synerise/README.md), source manifest, schema,
SELECT SQL, `run.py`, `supplement.py`, aggregate JSON and local boundary tests are
under `analysis/synerise/`. Raw archive/files are under ignored
`data/external/synerise/`. Query source SQL and hashes/timings are in `results.json`.
No client-level output is published. Exact duplicate and identity diagnostics,
all four snapshot definitions, 1/7/30-day funnels and historical coverage were
executed on the complete downloaded sources. No models were trained. Two local
tests passed for temporal boundaries, duplicate
occasion grouping, strict ordering, window bounds and same-SKU linkage; Ruff lint
and formatting passed. Automated report checks reconcile all A/B/C label counts,
full follow-up and strictly historical coverage.

Unresolved: publisher explanation of differing counts/dimensions, timestamp
timezone, actual orders/refunds/status, logging completeness, historical product
attribute availability, true identity completeness, compressed ClickHouse size,
full migration runtime and predictive quality. None is replaced by an invented
measurement. Source archive and extracted-file hashes were recorded; existing
REES46 artifacts, services and AIS were not opened for mutation. No commits/pushes.
"""
Path("docs/reports/phase-3.3-synerise-assessment.md").write_text(report)
print("Report and schema rendered from measured aggregates")
