"""Fetch and filter activities from Garmin Connect."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from garminconnect import Garmin

from garmin_stats.stats import is_aerobic, is_run


def get_recent_runs(client: Garmin, count: int = 5) -> list[dict[str, Any]]:
    """Return the most recent `count` running activities.

    Over-fetches a small buffer so non-run activities (rides, walks) don't
    starve the result.
    """
    activities = client.get_activities(0, max(count * 4, count))
    runs = [a for a in activities if is_run(a)]
    return runs[:count]


def get_activities_since(
    client: Garmin,
    start: date,
    predicate: Callable[[dict[str, Any]], bool],
) -> list[dict[str, Any]]:
    """Return activities from `start` (inclusive) through today matching `predicate`.

    `get_activities_by_date` paginates the full window for us; filtering
    client-side keeps every subtype (trail, treadmill, track) in play.
    """
    activities = client.get_activities_by_date(start.isoformat())
    return [a for a in activities if predicate(a)]


def get_runs_since(client: Garmin, start: date) -> list[dict[str, Any]]:
    """Return all running activities from `start` (inclusive) through today."""
    return get_activities_since(client, start, is_run)


def get_aerobic_since(client: Garmin, start: date) -> list[dict[str, Any]]:
    """Return runs *and* cross-training from `start` (inclusive) through today.

    Runs are a subset of this, so `weekly` derives both its mileage and its
    aerobic-minutes columns from a single request.
    """
    return get_activities_since(client, start, is_aerobic)


def get_activity_laps(client: Garmin, activity_id: int | str) -> list[dict[str, Any]]:
    """Return the lap (split) DTOs for a single activity."""
    data = client.get_activity_splits(activity_id)
    return data.get("lapDTOs") or []
