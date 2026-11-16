# coach-fingerprint

This repo turns tactical claims about coaches into numbers you can measure from free event data, then compares the coaches on one "fingerprint" page.

The first version tests the TacticalPathway thread breakdowns of **Sebastian Hoeneß** (Stuttgart), **Unai Emery** (Aston Villa) and **Francesco Farioli** (Porto). It uses StatsBomb open data.

```bash
pip install -e '.[dev]'
python -m coach_fingerprint.pipeline      # download events, one row per team per match -> data/
python -m coach_fingerprint.fingerprint   # rank each coach against his baseline -> output/fingerprint.json
python -m coach_fingerprint.report        # self-contained page -> output/index.html
pytest
```

A full run takes about 3 minutes. Event files are streamed and reduced, not stored.

## Data coverage (checked 2026-11-16)

StatsBomb open data doesn't cover any of the three coaches in his current job.

| Coach | What free data exists | Compared with |
|---|---|---|
| Hoeneß | Stuttgart's 2 Bundesliga games vs Leverkusen, 2023/24 (including 360 player positions) | The 16 other Bundesliga teams in their own games vs Leverkusen |
| Emery | Sevilla's full La Liga season 2015/16 (38 games), plus 2 Villarreal games in 2020/21 that aren't used | All 20 La Liga teams in 2015/16 |
| Farioli | Nothing | n/a |

Each coach is ranked inside his own comparison group, so the percentiles can sit side by side even though the leagues and seasons differ. Raw values from different contexts aren't comparable with each other.

To fill the gaps, any event feed in StatsBomb JSON format can be plugged in by adding a `Context` to `src/coach_fingerprint/coaches.py`.

## From claims to metrics

| Claim in the threads | Metric | How it is computed |
|---|---|---|
| Aggressive press | PPDA | Opponent passes in their own 60% of the pitch, divided by our tackles, interceptions and fouls in our attacking 60% |
| High press vs mid-block | Pressure height, share of pressures in the attacking third | StatsBomb `Pressure` events |
| 4-4-2 press commits players high | Players pressing in the opponent's third (360 data only) | Defenders inside the opponent's defensive third during their build-up passes |
| High defensive line | Centre-back defensive action height, and back-line height from 360 frames | Mean x of centre-back defensive actions. With 360 data, the mean of the two deepest defenders when the opponent passes in midfield |
| The 6 drops in (3-2 build-up) | Holding midfielder passes from the centre-back zone | Share of the defensive midfielder's own-half open-play passes played from the first 26 m |
| Full-backs push on | Full-back touch height | Mean x of full-back touches, the same measure Opta uses |
| Inverted full-backs | Full-back touch width, and middle-third touches in central lanes | Mean distance from the centre line, and share of middle-third touches inside the width of the penalty box |
| Aggressive counter-press | Counter-press actions per game, and losses won back within 5 seconds | StatsBomb `counterpress` flag. A regain is a won tackle, interception or recovery within 5 s of an open-play loss, after the opponent has touched the ball |
| Space left behind | xG conceded from counter-attacks, and shots conceded from through balls | Opponent shots with play pattern `From Counter`, or a key pass that was a through ball |

Pressing and build-up *shapes* (4-4-2, 4-1-3-2, 3-2, 2-3) need tracking data to measure properly. The page approximates them with the metrics above and with build-up maps showing where each position plays its own-half passes.

## Layout

```
src/coach_fingerprint/
  statsbomb.py        loader for StatsBomb open data (GitHub raw)
  metrics.py          per-team, per-match metrics
  coaches.py          which data covers which coach, and the baseline for each
  pipeline.py         download, compute, write data/team_matches_*.csv
  fingerprint.py      team averages, percentiles, build-up shapes
  report.py           claim verdicts and the HTML page
data/                 computed per-match metrics (small CSVs)
output/               fingerprint.json, fingerprint.csv, index.html
```

Data: [StatsBomb open data](https://github.com/statsbomb/open-data). Using it requires crediting StatsBomb.
