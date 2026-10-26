"""Reduce verified aggregate clock diagnostics without exporting source records."""

import json
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    verification = json.loads((ROOT / "verification.json").read_text())
    previous = json.loads((ROOT.parent / "results.json").read_text())
    result = {"files": {}, "daily_correlations": []}
    interior_daily = {}
    for name, info in verification["files"].items():
        if "hourly_by_date" not in info:
            continue
        hourly = info["hourly_by_date"]
        dates = sorted({x["date"] for x in hourly})
        hour_counts = Counter()
        weekday_totals = Counter()
        weekday_days = defaultdict(set)
        daily = Counter()
        monthly_hours = defaultdict(Counter)
        for row in hourly:
            if not dates[0] < row["date"] < dates[-1]:
                continue
            day = row["date"]
            n = row["n"]
            hour = int(row["hour"])
            hour_counts[hour] += n
            daily[day] += n
            weekday = date.fromisoformat(day).isoweekday()
            weekday_totals[weekday] += n
            weekday_days[weekday].add(day)
            monthly_hours[day[:7]][hour] += n
        changes = []
        keys = sorted(daily)
        for earlier, later in zip(keys, keys[1:], strict=False):
            changes.append(
                {"date": later, "previous_date": earlier, "ratio": daily[later] / daily[earlier]}
            )
        weekday_means = {k: weekday_totals[k] / len(weekday_days[k]) for k in weekday_totals}
        result["files"][name] = {
            "peak_hour_source_clock": hour_counts.most_common(1)[0][0],
            "lowest_hour_source_clock": min(hour_counts, key=hour_counts.get),
            "hour_counts_interior_days": dict(sorted(hour_counts.items())),
            "weekday_mean_events_per_observed_interior_day": weekday_means,
            "monthly_peak_hours": {k: v.most_common(1)[0][0] for k, v in monthly_hours.items()},
            "largest_day_to_day_increases": sorted(changes, key=lambda x: x["ratio"], reverse=True)[
                :5
            ],
            "largest_day_to_day_decreases": sorted(changes, key=lambda x: x["ratio"])[:5],
            "busiest_days": daily.most_common(5),
            "seconds_divisible_by_5_fraction": sum(
                x["n"] for x in info["seconds"] if x["second"] % 5 == 0
            )
            / info["row_count"],
            "non_multiple_of_5_events": sum(
                x["n"] for x in info["seconds"] if x["second"] % 5 != 0
            ),
            "exact_deduplication_only_rows": previous[name + "_duplicates"][0]["distinct_rows"],
            "first_day_events": sum(x["n"] for x in hourly if x["date"] == dates[0]),
            "last_day_events": sum(x["n"] for x in hourly if x["date"] == dates[-1]),
            "last_day_observed_hours": sorted(
                {x["hour"] for x in hourly if x["date"] == dates[-1]}
            ),
        }
        interior_daily[name] = daily
    names = sorted(interior_daily)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            days = sorted(interior_daily[first].keys() & interior_daily[second].keys())
            result["daily_correlations"].append(
                {
                    "first": first,
                    "second": second,
                    "interior_dates": len(days),
                    "pearson": statistics.correlation(
                        [interior_daily[first][d] for d in days],
                        [interior_daily[second][d] for d in days],
                    ),
                }
            )
    (ROOT / "diagnostic-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Clock summaries written; timezone inference intentionally omitted.")


if __name__ == "__main__":
    main()
