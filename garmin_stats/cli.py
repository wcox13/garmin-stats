"""CLI entry point for Garmin running stats."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)
from rich.console import Console

from garmin_stats.activities import (
    get_activity_laps,
    get_aerobic_since,
    get_recent_runs,
    get_runs_since,
)
from garmin_stats.auth import get_client
from garmin_stats.format import (
    format_runs_table,
    format_weekly_table,
    format_workouts_table,
)
from garmin_stats.stats import build_workout, weekly_summary, window_starts

console = Console()


def _cmd_runs(client, args) -> None:
    runs = get_recent_runs(client, args.count)
    console.print(format_runs_table(runs))


def _cmd_weekly(client, args) -> None:
    # Fetch from the Monday that starts the oldest week in the window. Runs and
    # cross-training come back together, so one request feeds both the mileage
    # and the aerobic-minutes columns.
    oldest_monday = window_starts(args.weeks, date.today(), args.current)[0]
    activities = get_aerobic_since(client, oldest_monday)
    buckets = weekly_summary(activities, weeks=args.weeks, include_current=args.current)
    console.print(format_weekly_table(buckets))


def _cmd_workouts(client, args) -> None:
    # Rolling window of the last N weeks, up to today.
    start = date.today() - timedelta(weeks=args.weeks)
    runs = get_runs_since(client, start)

    # Detecting workouts needs per-run lap data — one API call each.
    workouts = []
    with console.status(f"Analyzing {len(runs)} runs for workouts…"):
        for run in runs:
            laps = get_activity_laps(client, run["activityId"])
            workout = build_workout(run, laps)
            if workout is not None:
                workouts.append(workout)

    console.print(format_workouts_table(workouts, args.weeks))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="garmin-stats",
        description="Summarize Garmin Connect running activity.",
    )
    sub = parser.add_subparsers(dest="command")

    p_runs = sub.add_parser("runs", help="Show your most recent runs.")
    p_runs.add_argument(
        "-n", "--count", type=int, default=5,
        help="Number of recent runs to show (default: 5).",
    )
    p_runs.set_defaults(func=_cmd_runs)

    p_weekly = sub.add_parser("weekly", help="Weekly running mileage totals.")
    p_weekly.add_argument(
        "-w", "--weeks", type=int, default=12,
        help="Number of completed weeks to summarize (default: 12).",
    )
    p_weekly.add_argument(
        "--no-current", dest="current", action="store_false",
        help="Omit the in-progress week (shown by default).",
    )
    p_weekly.set_defaults(func=_cmd_weekly, current=True)

    p_workouts = sub.add_parser(
        "workouts", help="List interval workouts (runs with fast laps)."
    )
    p_workouts.add_argument(
        "-w", "--weeks", type=int, default=12,
        help="Number of weeks to look back (default: 12).",
    )
    p_workouts.set_defaults(func=_cmd_workouts)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Default to the `runs` command when none is given.
    if not getattr(args, "command", None):
        args = parser.parse_args(["runs", *(argv or [])])

    if getattr(args, "count", 1) < 1:
        parser.error("--count must be at least 1")
    if getattr(args, "weeks", 1) < 1:
        parser.error("--weeks must be at least 1")

    # The library logs benign 429 warnings while cycling through its login
    # strategy chain (it recovers on a later strategy). Suppress them so only
    # real failures — which surface as raised exceptions — reach the user.
    logging.getLogger("garminconnect").setLevel(logging.ERROR)

    try:
        client = get_client()
    except GarminConnectTooManyRequestsError:
        print(
            "Garmin rate-limited this IP (HTTP 429). Wait a few minutes and "
            "try again — repeated login attempts trigger this.",
            file=sys.stderr,
        )
        return 1
    except GarminConnectAuthenticationError as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        return 1

    args.func(client, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
