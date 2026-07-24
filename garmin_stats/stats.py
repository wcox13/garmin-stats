"""Aggregation logic for activity stats.

Pure functions (no network), so they're straightforward to unit-test. `today`
is injectable for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from garmin_stats.format import meters_to_miles


# A lap counts as an "interval" if its average pace is at least this fast.
INTERVAL_PACE_SEC_PER_MILE = 7 * 60 + 30  # 7:30 / mile


@dataclass
class WeekBucket:
    start: date  # Monday that begins the week
    miles: float
    runs: int
    longest: float = 0.0  # longest single run that week, in miles


@dataclass
class Workout:
    date: date
    interval_laps: int
    total_interval_distance_m: float
    total_interval_duration_s: float


def _activity_date(activity: dict[str, Any]) -> date | None:
    # startTimeLocal looks like "2026-07-08 06:31:22"; keep the date part.
    stamp = (activity.get("startTimeLocal") or "").split(" ")[0]
    try:
        return datetime.strptime(stamp, "%Y-%m-%d").date()
    except ValueError:
        return None


def week_start(d: date) -> date:
    """Monday of the week containing `d` (ISO week, Monday start)."""
    return d - timedelta(days=d.weekday())


def window_starts(weeks: int, today: date) -> list[date]:
    """Monday start-dates for the last `weeks` *completed* weeks, oldest first.

    The week containing `today` is partial, so it is excluded; the newest
    bucket is the most recent fully-finished week.
    """
    newest = week_start(today) - timedelta(weeks=1)
    return [newest - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]


def weekly_mileage(
    runs: list[dict[str, Any]], weeks: int = 12, today: date | None = None
) -> list[WeekBucket]:
    """Bucket running distance into the last `weeks` completed weeks, oldest first.

    Weeks are Monday-aligned. The current (partial) week is excluded. Runs
    outside the window are ignored.
    """
    if today is None:
        today = date.today()

    starts = window_starts(weeks, today)
    buckets = {s: WeekBucket(start=s, miles=0.0, runs=0) for s in starts}
    oldest, newest = starts[0], starts[-1]

    for activity in runs:
        d = _activity_date(activity)
        if d is None:
            continue
        ws = week_start(d)
        if ws < oldest or ws > newest:
            continue
        miles = meters_to_miles(activity.get("distance") or 0)
        bucket = buckets[ws]
        bucket.miles += miles
        bucket.runs += 1
        bucket.longest = max(bucket.longest, miles)

    return [buckets[s] for s in starts]


def lap_pace_sec_per_mile(lap: dict[str, Any]) -> float | None:
    """Average pace of a lap in seconds per mile, or None if not computable."""
    distance_m = lap.get("distance") or 0
    duration_s = lap.get("duration") or 0
    if distance_m <= 0 or duration_s <= 0:
        return None
    return duration_s / meters_to_miles(distance_m)


def is_interval_lap(
    lap: dict[str, Any], threshold_sec: float = INTERVAL_PACE_SEC_PER_MILE
) -> bool:
    """True if the lap's average pace is at least `threshold_sec` per mile."""
    pace = lap_pace_sec_per_mile(lap)
    return pace is not None and pace <= threshold_sec


def build_workout(
    run: dict[str, Any],
    laps: list[dict[str, Any]],
    threshold_sec: float = INTERVAL_PACE_SEC_PER_MILE,
) -> Workout | None:
    """Return a Workout if the run has any interval laps, else None.

    A run is a "workout" when at least one of its laps is an interval lap
    (average pace at least `threshold_sec` per mile).
    """
    intervals = [lap for lap in laps if is_interval_lap(lap, threshold_sec)]
    if not intervals:
        return None

    d = _activity_date(run)
    if d is None:
        return None

    return Workout(
        date=d,
        interval_laps=len(intervals),
        total_interval_distance_m=sum(lap["distance"] for lap in intervals),
        total_interval_duration_s=sum(lap["duration"] for lap in intervals),
    )
