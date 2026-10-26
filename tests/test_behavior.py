"""Definition-level tests for Phase 1.2 using controlled event sequences."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from ecommerce_analytics.analytics.behavior import BehaviorReport, analyze_behavior
from ecommerce_analytics.analytics.behavior_report import save_behavior_report
from ecommerce_analytics.analytics.exploration import ExplorationError

HEADER = ["event_time", "event_type", "product_id", "user_id", "user_session", "brand"]


def event(
    kind: str, second: int, session: str = "s1", user: str = "u1", day: int = 1, product: str = "p1"
) -> list[str]:
    return [f"2019-10-{day:02} 00:00:{second:02} UTC", kind, product, user, session, ""]


def analyze(tmp_path: Path, rows: list[list[str]]) -> BehaviorReport:
    path = tmp_path / "events.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return analyze_behavior(path)


@pytest.mark.parametrize(
    ("sequence", "presence", "strict", "cart_stage", "tie"),
    [
        ([("view", 0), ("cart", 1), ("purchase", 2)], 1, 1, 1, 0),
        ([("purchase", 0), ("cart", 1), ("view", 2)], 1, 0, 0, 0),
        ([("view", 0), ("purchase", 1)], 0, 0, 0, 0),
        ([("cart", 0), ("purchase", 1)], 0, 0, 0, 0),
        ([("view", 0), ("cart", 0), ("purchase", 0)], 1, 0, 0, 1),
        ([("view", 0), ("cart", 1), ("purchase", 1)], 1, 0, 1, 1),
        # Later valid events can complete a funnel despite an early purchase.
        ([("purchase", 0), ("view", 1), ("cart", 2), ("purchase", 3)], 1, 1, 1, 0),
    ],
)
def test_funnel_ordering(
    tmp_path: Path,
    sequence: list[tuple[str, int]],
    presence: int,
    strict: int,
    cart_stage: int,
    tie: int,
) -> None:
    tables = analyze(tmp_path, [event(kind, time) for kind, time in sequence]).tables
    funnels = tables["raw_funnel"].set_index("approach")
    assert funnels.loc["presence", "purchase_sessions"] == presence
    assert funnels.loc["chronological_strict", "purchase_sessions"] == strict
    assert funnels.loc["chronological_strict", "cart_sessions"] == cart_stage
    assert tables["ordering_anomalies"].iloc[0].tie_dependent_complete == tie


def test_presence_rates_and_across_product_funnel(tmp_path: Path) -> None:
    tables = analyze(
        tmp_path,
        [
            event("view", 0, product="a"),
            event("cart", 1, product="b"),
            event("purchase", 2, product="c"),
            event("cart", 0, session="s2"),
            event("view", 0, session="s3"),
        ],
    ).tables
    funnel = tables["raw_funnel"].iloc[1]
    assert funnel.all_sessions == 3
    assert funnel.purchase_sessions == 1
    assert funnel.view_to_cart == 0.5
    assert funnel.cart_to_purchase == 1
    assert funnel.view_to_purchase == 0.5
    assert funnel.purchase_share_all_sessions == pytest.approx(1 / 3)
    assert funnel.view_to_cart_dropoff == 0.5


def test_purchase_events_sessions_days_and_intervals(tmp_path: Path) -> None:
    tables = analyze(
        tmp_path,
        [
            event("purchase", 0),
            event("purchase", 1),
            event("purchase", 2),
            event("purchase", 0, session="s2", day=3),
            event("purchase", 0, session="s3", day=5),
            event("view", 0, session="s4", user="u2"),
        ],
    ).tables
    customer = tables["customers"].iloc[0]
    assert customer.customers == 2
    assert customer.purchasing_customers == 1
    assert customer.non_purchasing_customers == 1
    assert customer.purchase_events == 5
    assert customer.customer_purchasing_sessions == 3
    assert customer.customer_purchasing_days == 3
    assert customer.multiple_purchasing_days == 1
    interval = tables["purchase_intervals_days"].iloc[0]
    assert interval.observations == 2
    assert interval["median"] == 2
    assert tables["sessions"].iloc[0].multiple_purchase_events == 1


def test_exact_duplicates_do_not_change_funnel(tmp_path: Path) -> None:
    rows = [event("view", 0), event("cart", 1), event("purchase", 2)]
    tables = analyze(tmp_path, rows + [rows[-1], rows[-1]]).tables
    assert tables["raw_counts"].iloc[0].events == 5
    assert tables["deduplicated_counts"].iloc[0].events == 3
    assert tables["raw_counts"].iloc[0].purchase_events == 3
    assert tables["deduplicated_counts"].iloc[0].purchase_events == 1
    pd.testing.assert_frame_equal(tables["raw_funnel"], tables["deduplicated_funnel"])
    duplicate = tables["duplicate_event_types"].set_index("event_type").loc["purchase"]
    assert duplicate.excess_duplicate_rows == 2
    assert duplicate.duplicate_percentage == pytest.approx(100 * 2 / 3)
    assert tables["duplicate_multiplicity"].iloc[0].multiplicity == 3
    assert tables["duplicate_session_summary"].iloc[0].pairs_with_duplicates == 1


def test_missing_session_is_not_lost_from_customer_counts(tmp_path: Path) -> None:
    tables = analyze(tmp_path, [event("purchase", 0, session=""), event("view", 0)]).tables
    assert tables["quality"].iloc[0].excluded_session_events == 1
    assert tables["sessions"].iloc[0].sessions == 1
    assert tables["sessions"].iloc[0].with_purchase == 0
    customer = tables["customers"].iloc[0]
    assert customer.purchasing_customers == 1
    assert customer.purchasers_without_known_session == 1
    assert customer.customer_purchasing_sessions == 0


def test_shared_session_ids_do_not_join_customers_into_a_funnel(tmp_path: Path) -> None:
    report = analyze(
        tmp_path,
        [
            event("view", 0, user="u1"),
            event("cart", 1, user="u1"),
            event("purchase", 2, user="u2"),
            event("purchase", 3, user=""),
        ],
    )
    assert report.session_key == "(user_id, user_session)"
    assert report.tables["session_identity"].iloc[0].shared_by_multiple_customers == 1
    assert report.tables["sessions"].iloc[0].sessions == 3
    assert report.tables["raw_funnel"].iloc[1].purchase_sessions == 0
    assert report.tables["customers"].iloc[0].purchasing_customers == 1
    assert report.tables["quality"].iloc[0].excluded_customer_events == 1


def test_session_crosses_midnight_utc(tmp_path: Path) -> None:
    row = event("view", 0)
    row[0] = "2019-10-01 23:59:59 UTC"
    tables = analyze(tmp_path, [row, event("cart", 0, day=2), event("purchase", 1, day=2)]).tables
    assert tables["sessions"].iloc[0].spanning_utc_days == 1
    assert tables["duration_seconds"].iloc[0]["median"] == 2
    assert tables["raw_funnel"].iloc[1].purchase_sessions == 1


def test_missing_timestamp_still_contributes_presence(tmp_path: Path) -> None:
    row = event("view", 0)
    row[0] = ""
    tables = analyze(tmp_path, [row, event("cart", 1), event("purchase", 2)]).tables
    assert tables["quality"].iloc[0].missing_timestamps == 1
    assert tables["raw_funnel"].iloc[0].purchase_sessions == 1
    assert tables["raw_funnel"].iloc[1].purchase_sessions == 0
    assert tables["sessions"].iloc[0].incomplete_timestamps == 1


def test_horizons_censoring_and_tied_session_starts(tmp_path: Path) -> None:
    tables = analyze(
        tmp_path,
        [
            event("purchase", 0),
            event("purchase", 0, session="tie"),
            event("purchase", 0, session="later", day=5),
            event("view", 0, session="end", user="u2", day=31),
        ],
    ).tables
    horizons = tables["horizon_feasibility"].set_index("horizon_days")
    assert horizons.loc[7, "full_followup_anchors"] == 3
    assert horizons.loc[7, "full_followup_anchors_with_repeat"] == 2
    assert horizons.loc[30, "full_followup_anchors"] == 2
    assert horizons.loc[30, "anchors_with_equal_history_and_followup"] == 0
    assert tables["interval_quality"].iloc[0].tied_purchase_session_starts == 1


def test_ordering_anomalies(tmp_path: Path) -> None:
    tables = analyze(
        tmp_path,
        [
            event("purchase", 0),
            event("cart", 1),
            event("view", 2),
            event("purchase", 3, session="s2"),
        ],
    ).tables
    anomalies = tables["ordering_anomalies"].iloc[0]
    assert anomalies.purchase_before_first_view == 1
    assert anomalies.cart_before_first_view == 1
    assert anomalies.purchase_with_no_strictly_preceding_cart == 2


def test_header_only_and_report_export(tmp_path: Path) -> None:
    report = analyze(tmp_path, [])
    assert report.tables["quality"].iloc[0].events == 0
    assert report.tables["raw_funnel"].iloc[0].all_sessions == 0
    assert pd.isna(report.tables["raw_funnel"].iloc[0].view_to_purchase)
    save_behavior_report(report, tmp_path / "output", tmp_path / "report.md")
    text = (tmp_path / "report.md").read_text()
    assert "7 — Recommendations" in text
    assert (tmp_path / "output" / "raw_funnel.csv").exists()
    with pytest.raises(ValueError, match="overwrite"):
        save_behavior_report(report, tmp_path / "output", Path(report.source))


def test_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(ExplorationError):
        analyze_behavior(tmp_path / "missing.csv")
    path = tmp_path / "broken.csv"
    path.write_text("event_time\nnot-a-time\n")
    with pytest.raises(ExplorationError, match="Missing required columns"):
        analyze_behavior(path)


def test_utc_days_and_outside_october_are_retained(tmp_path: Path) -> None:
    first = event("purchase", 0)
    first[0] = "2019-10-01 01:00:00+03:00"  # September 30 UTC
    second = event("purchase", 0)
    second[0] = "2019-10-01 02:00:00+03:00"  # Same UTC day and session
    tables = analyze(tmp_path, [first, second]).tables
    assert tables["quality"].iloc[0].events == 2
    assert tables["quality"].iloc[0].outside_october == 2
    assert tables["sessions"].iloc[0].outside_october == 1
    assert tables["customers"].iloc[0].customer_purchasing_days == 1
    assert str(tables["daily_purchase_activity"].iloc[0].day_utc.date()) == "2019-09-30"
