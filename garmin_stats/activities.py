"""Fetch and filter activities from Garmin Connect."""

from __future__ import annotations

from datetime import date
from typing import Any

from garminconnect import Garmin


def _is_run(activity: dict[str, Any]) -> bool:
    type_key = (activity.get("activityType") or {}).get("typeKey", "")
    return "running" in type_key


def get_recent_runs(client: Garmin, count: int = 5) -> list[dict[str, Any]]:
    """Return the most recent `count` running activities.

    Over-fetches a small buffer so non-run activities (rides, walks) don't
    starve the result.
    """
    activities = client.get_activities(0, max(count * 4, count))
    runs = [a for a in activities if _is_run(a)]
    return runs[:count]


def get_runs_since(client: Garmin, start: date) -> list[dict[str, Any]]:
    """Return all running activities from `start` (inclusive) through today.

    `get_activities_by_date` paginates the full window for us; we filter to
    runs client-side so every running subtype (trail, treadmill, track) counts.
    """
    activities = client.get_activities_by_date(start.isoformat())
    return [a for a in activities if _is_run(a)]


def get_activity_laps(client: Garmin, activity_id: int | str) -> list[dict[str, Any]]:
    """Return the lap (split) DTOs for a single activity."""
    data = client.get_activity_splits(activity_id)
    return data.get("lapDTOs") or []
