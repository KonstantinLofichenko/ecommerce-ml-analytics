# Customer snapshot features — Phase 2.3

Build a prior-purchaser cohort at midnight UTC on 2019-11-01, 2019-12-01,
2020-01-01 and 2020-02-01. The source is `raw_events` in the existing
`data/processed/ecommerce.duckdb`. No session/customer summaries or comparison
views feed these calculations; they can contain post-snapshot information.

## Reproduction

Disconnect DBeaver or any other application holding the database open first.
From the repository root:

```bash
source .venv/bin/activate
python scripts/build_customer_features.py
pytest
ruff check .
ruff format --check .
```

Defaults write `customer_snapshot_features` and the aggregate
`customer_snapshot_build_audit` table in the existing database,
`docs/reports/phase-2.3-features.md`, and six aggregate CSV files under
`data/processed/phase-2.3/`. The database and CSV files are ignored by Git.
No full feature rows are exported automatically. Rebuilding replaces only these
two tables, inside a transaction; validation failure restores the previous result.
Existing raw, session, customer and manifest tables remain intact. Rebuild the
source database before rebuilding features if the source CSVs change.

Options `--database`, `--report`, and `--output` change paths. Repeated
`--prediction-date YYYY-MM-DD` arguments replace the default set; they must be
unique dates with observed follow-up through their target-window end. Dates
without supplied reference counts are marked as such in reconciliation output.

## Cohort, feature and target boundaries

For a prediction time t, include each known customer with at least one raw
purchase timestamp strictly less than t. One row represents `(prediction_date,
user_id)`. `target_14d` is 1 if any purchase occurs in **[t, t + 14 days)**;
otherwise it is 0. Future events appear only in label SQL and validation queries.

| Feature | Definition using only events before t |
| --- | --- |
| `days_since_last_purchase` | Fractional elapsed UTC days since latest purchase |
| `purchase_sessions_30d` | Distinct known customer/session pairs purchasing in [t−30d, t) |
| `sessions_30d` | Distinct known customer/session pairs active in [t−30d, t) |
| `view_events_30d` | Raw view events in [t−30d, t) |
| `cart_events_30d` | Raw cart events in [t−30d, t) |
| `remove_events_30d` | Raw remove_from_cart events in [t−30d, t) |
| `purchase_events_30d` | Raw purchase events in [t−30d, t) |
| `distinct_products_30d` | Distinct nonmissing products across all event types in [t−30d, t) |
| `days_since_last_event` | Fractional elapsed UTC days since latest event |
| `historical_purchasing_sessions` | Distinct known purchasing customer/session pairs before t |

Thirty days means 30 × 24 hours, not a calendar month. UTC source times are the
normalized `event_time_utc` TIMESTAMP values from ingestion; client timezone does
not change the feature bounds. Counts use raw records, retaining duplicates.
Sessions use typed STRUCT keys for the exact `(user_id, user_session)` pair.

Null customer IDs cannot form cohort rows. Null timestamps cannot establish any
window and are excluded from the temporal calculations, with source-quality
counts reported. Null session IDs are excluded only from session counts: their
events still affect eligibility, target, recency, event counts and distinct
products. Null product IDs do not contribute to distinct-product counts. A
customer with no trailing activity has zero counts; recencies still use their
older observed history. Eligibility guarantees both recencies exist.

A session can straddle a snapshot; only its earlier events affect features.
A purchase after t can set the target even if that session already purchased
before t. This predicts an observed future purchase event, not necessarily a new
order or a new purchasing session. No whole-session purchase flag is used.

## Validation and reference counts

A composite primary key, NOT NULL columns, binary target and count/recency
constraints protect the table. Independent raw queries compare the complete
eligible and positive customer-key sets. Temporal audits record contributor
bounds and require zero out-of-window counts. Tests use synthetic histories to
verify exact boundaries, nulls, cross-snapshot sessions, duplicates and future
perturbation invariance. Transactional rollback and report export are also tested.

| Snapshot | Expected eligible customers | Expected positive labels |
| --- | --- | --- |
| 2019-11-01 | 25,762 | 2,373 |
| 2019-12-01 | 52,523 | 3,382 |
| 2020-01-01 | 72,225 | 3,699 |
| 2020-02-01 | 92,652 | 4,380 |

These are the supplied Phase 2.1 references, not hardcoded outcomes. The build
report shows measured counts, differences, label rates, null checks and feature
statistics. Discrepancies remain explicit; definitions are not adjusted to force
agreement. Structural/temporal validation errors fail and roll back the build.

## Inspect the dataset

```python
import duckdb

with duckdb.connect("data/processed/ecommerce.duckdb", read_only=True) as con:
    print(
        con.sql(
            "SELECT prediction_date, count(*) AS rows, sum(target_14d) AS positives "
            "FROM customer_snapshot_features GROUP BY 1 ORDER BY 1"
        )
    )
    print(con.sql("SELECT * FROM customer_snapshot_features LIMIT 5"))
    print(con.sql("SELECT * FROM customer_snapshot_build_audit ORDER BY prediction_date"))
```

## Limits for future modeling

History is observed only from October 2019; lifetime recency/frequency is unknown.
Later snapshots have longer observed history. Repeated customers and overlapping
history across snapshots require chronological validation, not a random row
split. These rows concern previous purchasers, not all visitors or cold-start
customers. Missing sessions undercount session features; duplicates inflate raw
event counts. Last observed source time is a follow-up guard, not proof of
continuous logging or genuine customer availability. Label zero means no
recorded purchase in the covered window, not proof of no real-world purchase.
No deduplication policy, model split, training, or deployment is introduced.
