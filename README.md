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

`weekly` shows two things side by side: running volume and total aerobic time.

The distance columns (`Runs`, `Miles`, `Longest`, `Mileage`) count running
activities only — trail/treadmill/track included, everything else excluded.

The `Aerobic` column totals **elapsed minutes** across runs *and* cross-training
(Garmin's `indoor_cardio` / `cardio` types); strength training and surfing don't
count. Where a week mixes both, the cross-training share is shown in
parentheses — `188 (24)` means 188 aerobic minutes of which 24 were
cross-training. The `Minutes` bar encodes the same split by color: green for
running, magenta for cross-training. Minutes come from each activity's elapsed
`duration` rather than moving time, since indoor cardio reports a moving
duration of zero.

Weeks are Monday-aligned and only *completed* weeks are shown — the current,
partial week is excluded, so the last row is the most recently finished week.
The peak mileage week is highlighted on its bar; the peak aerobic week is
highlighted on its number, so the bar keeps its run/cross-training coloring.

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

```
  Week of   Runs   Miles   Longest   Mileage          Aerobic   Minutes
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Jun 22       5    19.8       4.9   ██████████████   188 (24)  ██████████████
  Jun 29       5    19.9       5.3   ██████████████        187  ██████████████
  Jul 06       5    20.2       5.1   ██████████████        190  ██████████████
  Aug 03       0     0.0         –                          121  ████████████

             4 completed weeks · 60.0 mi · 15 runs · 11.4 aerobic hrs
            avg 15.0 mi/week · 3.8 runs/week · 171 aerobic min/week
                            █ run   █ cross-training
```

## Layout

- `garmin_stats/auth.py` — authenticated Garmin client (token resume + login)
- `garmin_stats/activities.py` — fetch + filter activities (runs, aerobic)
- `garmin_stats/stats.py` — activity predicates, weekly aggregation, workout
  detection (pure functions — no network)
- `garmin_stats/format.py` — unit conversion + rich table rendering
- `garmin_stats/cli.py` — argparse entry point (`runs`, `weekly`, `workouts`)
