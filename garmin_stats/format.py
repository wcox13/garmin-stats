"""Unit conversion and table rendering for activity stats.

Conversion helpers are pure (unit-testable without network). Rendering builds
`rich` tables for colored terminal output.
"""

from __future__ import annotations

from typing import Any

from rich import box
from rich.table import Table
from rich.text import Text

METERS_PER_MILE = 1609.344

# Shared color scheme. Green/magenta rather than green/cyan for the stacked
# bar: the latter pair is hard to tell apart with deuteranopia.
PEAK_STYLE = "bold yellow"
BAR_STYLE = "green"
CROSS_BAR_STYLE = "magenta"
DIM_STYLE = "dim"

# Sized so the weekly table (two bars plus six data columns) fits in 80 columns.
BAR_WIDTH = 14


def meters_to_miles(meters: float) -> float:
    return meters / METERS_PER_MILE


def format_duration(seconds: float | None) -> str:
    """Format a duration as 'm:ss' (or 'h:mm:ss' past an hour), '--:--' if none."""
    if not seconds or seconds < 0:
        return "--:--"
    total = round(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def pace_per_mile(distance_m: float | None, duration_s: float | None) -> str:
    """Return pace as 'mm:ss' per mile, or '--:--' if not computable."""
    if not distance_m or not duration_s:
        return "--:--"
    miles = meters_to_miles(distance_m)
    if miles <= 0:
        return "--:--"
    seconds_per_mile = duration_s / miles
    minutes, seconds = divmod(round(seconds_per_mile), 60)
    return f"{minutes:02d}:{seconds:02d}"


def _run_date(activity: dict[str, Any]) -> str:
    # startTimeLocal looks like "2026-07-08 06:31:22"; keep the date part.
    return (activity.get("startTimeLocal") or "").split(" ")[0] or "----------"


def format_runs_table(runs: list[dict[str, Any]]) -> Table | str:
    """Build a rich table of recent runs (or a message when there are none)."""
    if not runs:
        return "No runs found."

    table = Table(box=box.SIMPLE_HEAVY, header_style="bold")
    table.add_column("Date")
    table.add_column("Name")
    table.add_column("Distance", justify="right")
    table.add_column("Pace", justify="right")

    for a in runs:
        distance_m = a.get("distance")
        duration_s = a.get("duration")
        table.add_row(
            _run_date(a),
            (a.get("activityName") or "").strip() or "(unnamed)",
            f"{meters_to_miles(distance_m or 0):.2f} mi",
            Text(f"{pace_per_mile(distance_m, duration_s)} /mi", style="cyan"),
        )
    return table


def _bar(value: float, max_value: float, width: int = BAR_WIDTH) -> str:
    """A proportional bar of block chars scaled to `max_value`."""
    if max_value <= 0 or value <= 0:
        return ""
    filled = max(1, round(value / max_value * width))
    return "█" * filled


def _stacked_bar(
    primary: float, secondary: float, max_value: float, width: int = BAR_WIDTH
) -> Text:
    """A two-segment bar whose total length encodes `primary + secondary`.

    The total block count is rounded first and then split between the
    segments, so the bar's overall length stays faithful to the value it
    represents (rounding each segment independently lets the length drift). A
    nonzero segment is floored at one block, borrowed from the larger segment,
    so a single short cross-training session doesn't vanish.
    """
    total_value = primary + secondary
    if max_value <= 0 or total_value <= 0:
        return Text("")

    total = max(1, round(total_value / max_value * width))
    first = round(primary / total_value * total)
    second = total - first

    if secondary > 0 and second == 0 and first > 1:
        first, second = first - 1, 1
    elif primary > 0 and first == 0 and second > 1:
        first, second = 1, second - 1

    return Text.assemble(("█" * first, BAR_STYLE), ("█" * second, CROSS_BAR_STYLE))


def format_weekly_table(buckets: list[Any]) -> Table | str:
    """Build a rich table of weekly-mileage buckets (see stats.WeekBucket).

    Reads attributes by duck-typing to avoid a circular import with stats.
    Highlights the peak week and draws a colored bar per week.
    """
    if not buckets:
        return "No data."

    peak = max((b.miles for b in buckets), default=0.0)
    peak_minutes = max((b.minutes for b in buckets), default=0.0)

    n = len(buckets)
    total_miles = sum(b.miles for b in buckets)
    total_runs = sum(b.runs for b in buckets)
    total_minutes = sum(b.minutes for b in buckets)
    caption = Text.assemble(
        f"{n} completed weeks · {total_miles:.1f} mi · {total_runs} runs · "
        f"{total_minutes / 60:.1f} aerobic hrs\n"
        f"avg {total_miles / n:.1f} mi/week · {total_runs / n:.1f} runs/week · "
        f"{total_minutes / n:.0f} aerobic min/week\n",
        ("█", BAR_STYLE),
        (" run   ", DIM_STYLE),
        ("█", CROSS_BAR_STYLE),
        (" cross-training", DIM_STYLE),
    )

    table = Table(box=box.SIMPLE_HEAVY, header_style="bold", caption=caption)
    table.add_column("Week of")
    table.add_column("Runs", justify="right")
    table.add_column("Miles", justify="right")
    table.add_column("Longest", justify="right")
    table.add_column("Mileage")
    table.add_column("Aerobic", justify="right")
    table.add_column("Minutes")

    for b in buckets:
        is_peak = peak > 0 and b.miles == peak
        miles_style = PEAK_STYLE if is_peak else ""
        bar_style = PEAK_STYLE if is_peak else BAR_STYLE
        longest = f"{b.longest:.1f}" if b.longest > 0 else "–"

        # The peak *minutes* week is marked on the number, not the bar —
        # recoloring the bar would destroy the run/cross-training split.
        is_peak_minutes = peak_minutes > 0 and b.minutes == peak_minutes
        minutes = Text(
            f"{b.minutes:.0f}" if b.minutes > 0 else "–",
            style=PEAK_STYLE if is_peak_minutes else "",
        )
        # Parenthesize the cross-training share only when it's a share of
        # something — on a run-free week the fully-magenta bar already says it.
        if b.cross_minutes > 0 and b.run_minutes > 0:
            minutes.append(f" ({b.cross_minutes:.0f})", style=DIM_STYLE)

        table.add_row(
            b.start.strftime("%b %d"),  # e.g. "Apr 20"
            str(b.runs),
            Text(f"{b.miles:.1f}", style=miles_style),
            Text(longest, style=DIM_STYLE),
            Text(_bar(b.miles, peak), style=bar_style),
            minutes,
            _stacked_bar(b.run_minutes, b.cross_minutes, peak_minutes),
        )
    return table


def format_workouts_table(workouts: list[Any], weeks: int) -> Table | str:
    """Build a rich table of workouts (see stats.Workout).

    Reads attributes by duck-typing to avoid a circular import with stats.
    """
    if not workouts:
        return f"No workouts found in the past {weeks} weeks."

    caption = f"{len(workouts)} workouts over the past {weeks} weeks"
    table = Table(box=box.SIMPLE_HEAVY, header_style="bold", caption=caption)
    table.add_column("Date")
    table.add_column("Intervals", justify="right")
    table.add_column("Total dist", justify="right")
    table.add_column("Avg dist", justify="right")
    table.add_column("Avg time", justify="right")
    table.add_column("Avg pace", justify="right")

    for w in workouts:
        total_mi = meters_to_miles(w.total_interval_distance_m)
        avg_dist_m = w.total_interval_distance_m / w.interval_laps
        avg_time_s = w.total_interval_duration_s / w.interval_laps
        pace = pace_per_mile(w.total_interval_distance_m, w.total_interval_duration_s)
        table.add_row(
            w.date.isoformat(),
            str(w.interval_laps),
            f"{total_mi:.2f} mi",
            f"{meters_to_miles(avg_dist_m):.2f} mi",
            format_duration(avg_time_s),
            Text(f"{pace} /mi", style="cyan"),
        )
    return table
