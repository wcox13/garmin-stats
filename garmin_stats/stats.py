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


# Garmin's typeKey for the cross-training sessions we count as aerobic work.
# Both spellings appear in the wild depending on how the activity was logged.
CARDIO_TYPE_KEYS = frozenset({"indoor_cardio", "cardio"})


@dataclass
class WeekBucket:
    start: date  # Monday that begins the week
    miles: float
    runs: int
    longest: float = 0.0  # longest single run that week, in miles
    run_minutes: float = 0.0
    cross_minutes: float = 0.0  # cross-training (cardio) minutes
    partial: bool = False  # the in-progress week, still accumulating

    @property
    def minutes(self) -> float:
        """Total aerobic minutes: running plus cross-training."""
        return self.run_minutes + self.cross_minutes


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


def activity_type(activity: dict[str, Any]) -> str:
    return (activity.get("activityType") or {}).get("typeKey") or ""


def is_run(activity: dict[str, Any]) -> bool:
    """True for any running subtype (trail, treadmill, track, …)."""
    return "running" in activity_type(activity)


def is_cross_training(activity: dict[str, Any]) -> bool:
    """True for the cardio sessions that stand in for cross-training."""
    return activity_type(activity) in CARDIO_TYPE_KEYS


def is_aerobic(activity: dict[str, Any]) -> bool:
    """True for activities that count toward weekly aerobic minutes."""
    return is_run(activity) or is_cross_training(activity)


def activity_minutes(activity: dict[str, Any]) -> float:
    """Elapsed activity time in minutes.

    Uses `duration` rather than `movingDuration`: indoor cardio reports a
    moving duration of 0, which would zero out every cross-training session.
    """
    return (activity.get("duration") or 0) / 60


def week_start(d: date) -> date:
    """Monday of the week containing `d` (ISO week, Monday start)."""
    return d - timedelta(days=d.weekday())


def window_starts(
    weeks: int, today: date, include_current: bool = False
) -> list[date]:
    """Monday start-dates for the last `weeks` *completed* weeks, oldest first.

    The week containing `today` is partial, so it is not one of the `weeks`;
    with `include_current` it is appended as an extra, final start-date. Either
    way `weeks` counts finished weeks, so the flag never shifts the window back
    in time.
    """
    current = week_start(today)
    newest = current - timedelta(weeks=1)
    starts = [newest - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    if include_current:
        starts.append(current)
    return starts


def weekly_summary(
    activities: list[dict[str, Any]],
    weeks: int = 12,
    today: date | None = None,
    include_current: bool = False,
) -> list[WeekBucket]:
    """Bucket aerobic activity into the last `weeks` completed weeks, oldest first.

    Weeks are Monday-aligned. With `include_current`, the in-progress week is
    appended as an extra bucket flagged `partial` — it holds however much of
    the week has happened so far, so callers should keep it out of totals and
    averages. Activities outside the window are ignored.

    Distance columns (miles, runs, longest) count *runs only*, so they keep
    meaning what they always meant; minutes accumulate from runs and
    cross-training alike, split across `run_minutes` and `cross_minutes`.
    Non-aerobic activities (strength, surfing) are ignored entirely.
    """
    if today is None:
        today = date.today()

    starts = window_starts(weeks, today, include_current)
    current = week_start(today)
    buckets = {
        s: WeekBucket(start=s, miles=0.0, runs=0, partial=(s == current))
        for s in starts
    }
    oldest, newest = starts[0], starts[-1]

    for activity in activities:
        if not is_aerobic(activity):
            continue
        d = _activity_date(activity)
        if d is None:
            continue
        ws = week_start(d)
        if ws < oldest or ws > newest:
            continue

        bucket = buckets[ws]
        minutes = activity_minutes(activity)
        if is_run(activity):
            miles = meters_to_miles(activity.get("distance") or 0)
            bucket.miles += miles
            bucket.runs += 1
            bucket.longest = max(bucket.longest, miles)
            bucket.run_minutes += minutes
        else:
            bucket.cross_minutes += minutes

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
