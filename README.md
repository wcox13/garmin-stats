# garmin-stats

A small CLI to summarize your Garmin Connect activity. First feature: pace and
distance of your last N runs.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m garmin_stats.cli                    # last 5 runs (default)
python -m garmin_stats.cli runs --count 10    # last 10 runs
python -m garmin_stats.cli weekly             # weekly mileage, last 12 weeks
python -m garmin_stats.cli weekly --weeks 8   # weekly mileage, last 8 weeks
python -m garmin_stats.cli workouts           # interval workouts, last 12 weeks
python -m garmin_stats.cli workouts --weeks 6 # interval workouts, last 6 weeks
```

`workouts` lists runs that contain at least one *interval lap* — a lap whose
average pace is 7:30/mi or faster. For each such run it shows the number of
interval laps, their combined distance, the average interval-lap distance, and
the average interval-lap pace (distance-weighted). Detecting workouts requires
one lap-data request per run in the window, so this command is slower than the
others (a spinner shows progress).

`weekly` counts running activities only (trail/treadmill/track included;
non-runs such as rides, walks, and surfing are excluded). Weeks are
Monday-aligned and only *completed* weeks are shown — the current, partial
week is excluded, so the last row is the most recently finished week. Each row
shows total miles, the longest single run, and a colored bar (via `rich`); the
peak week is highlighted.

On first run you'll be prompted for your Garmin email, password, and (if
enabled) an MFA code. OAuth tokens are cached under `~/.garminconnect` and
auto-refreshed, so subsequent runs don't prompt for login.

## Example output

```
Date        Name              Distance  Pace
----------  ----------------  --------  ---------
2026-07-08  Morning Run       5.02 mi   08:14 /mi
2026-07-06  Tempo             4.00 mi   07:31 /mi
...
```

## Layout

- `garmin_stats/auth.py` — authenticated Garmin client (token resume + login)
- `garmin_stats/activities.py` — fetch + filter running activities
- `garmin_stats/stats.py` — weekly aggregation + workout detection (pure functions)
- `garmin_stats/format.py` — unit conversion + rich table rendering
- `garmin_stats/cli.py` — argparse entry point (`runs`, `weekly`, `workouts`)
