"""Aggregate per-match rows into a coach fingerprint.

Each coach's team is ranked against its own baseline (the other teams in the
same data set), so a percentile of 90 means 'more of this than 90% of the
teams it can fairly be compared with'. Percentiles are what the chart plots;
raw values travel with them for the tooltip and the table.

    python -m coach_fingerprint.fingerprint   # writes output/fingerprint.json + .csv
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .coaches import CONTEXTS
from .metrics import average_shape

ROOT = Path(__file__).resolve().parents[2]
DATA, OUT = ROOT / "data", ROOT / "output"


@dataclass
class Metric:
    key: str
    label: str
    group: str
    unit: str
    claim: str
    # +1: a higher raw value means more of the trait in the label. -1: lower does.
    direction: int = 1
    digits: int = 1
    per_match_sum: bool = False


METRICS = [
    Metric("ppda", "Pressing intensity (PPDA, lower = more intense)", "Pressing", "", "All three press aggressively", -1),
    Metric("press_height_m", "Average pressure height", "Pressing", "m from own goal", "High press vs mid-block"),
    Metric("high_press_share", "Pressures in the attacking third", "Pressing", "%", "High press vs mid-block", digits=0),
    Metric("press_commit_360", "Players pressing in opponent's third (360)", "Pressing", "players", "4-4-2 press commits 2 forwards plus wide men"),
    Metric("cb_action_height_m", "Centre-back defensive action height", "Defensive line", "m from own goal", "High defensive line"),
    Metric("line_height_360_m", "Back-line height in midfield phase (360)", "Defensive line", "m from own goal", "High defensive line"),
    Metric("fb_touch_height_m", "Full-back touch height", "Full-backs", "m from own goal", "Full-backs push on"),
    Metric("fb_touch_width_m", "Full-back narrowness (touch width, lower = narrower)", "Full-backs", "m from centre", "Inverted full-backs", -1),
    Metric("fb_central_share", "Full-back middle-third touches in central lanes", "Full-backs", "%", "Inverted full-backs", digits=0),
    Metric("dm_drop_share", "Holding midfielder passes from the centre-back zone", "Build-up", "%", "The 6 drops into the back line (3-2 build-up)", digits=0),
    Metric("counterpress_actions", "Counter-press actions per game", "Counter-press", "per game", "Aggressive counter-press", digits=0),
    Metric("regain_5s_rate", "Ball losses won back within 5 seconds", "Counter-press", "%", "Aggressive counter-press", digits=0),
    Metric("counter_xg_conceded", "xG conceded from counter-attacks", "Space behind", "xG per game", "Space left behind a high line", digits=2),
    Metric("through_ball_shots_conceded", "Shots conceded from through balls", "Space behind", "per game", "Space left behind a high line", digits=2),
    Metric("possession", "Possession (pass share)", "Context", "%", "Context for every other number", digits=0),
]
PCT_KEYS = {"dm_drop_share", "high_press_share", "fb_central_share", "regain_5s_rate", "possession"}


def _percentile(values: pd.Series, subject: str, direction: int) -> tuple[float, int, int]:
    v = values.dropna() * direction
    if subject not in v.index:
        return np.nan, 0, len(v)
    rank = int((v > v[subject]).sum()) + 1  # 1 = most of the trait
    n = len(v)
    pct = 100 * (v < v[subject]).sum() / (n - 1) if n > 1 else np.nan
    return float(pct), rank, n


def build() -> dict:
    out = {"metrics": [asdict(m) for m in METRICS], "coaches": []}
    rows = []
    for ctx in CONTEXTS:
        coach = {
            "key": ctx.key, "coach": ctx.coach, "team": ctx.team,
            "sample": ctx.sample, "baseline": ctx.baseline, "values": {}, "shapes": [],
        }
        path = DATA / f"team_matches_{ctx.key}.csv"
        if not path.exists():
            out["coaches"].append(coach)
            continue
        df = pd.read_csv(path)
        df["is_subject"] = df.is_subject.astype(bool)
        base = df[df.in_baseline & ((df.team != ctx.team) | df.is_subject)]
        team_means = base.groupby("team").mean(numeric_only=True)
        coach["games"] = int(df.is_subject.sum())
        for m in METRICS:
            if m.key not in team_means:
                continue
            col = team_means[m.key]
            if col.dropna().get(ctx.team) is None:
                continue
            pct, rank, n = _percentile(col, ctx.team, m.direction)
            scale = 100 if m.key in PCT_KEYS else 1
            coach["values"][m.key] = {
                "value": round(float(col[ctx.team]) * scale, 3),
                "baseline_median": round(float(col.median()) * scale, 3),
                "percentile": round(pct, 1),
                "rank": rank,
                "of": n,
            }
            rows.append({"coach": ctx.coach, "metric": m.label, **coach["values"][m.key]})
        subj = df[df.is_subject]
        coach["formations"] = subj.formation.astype(str).value_counts().to_dict()
        shape_path = DATA / f"shapes_{ctx.key}.json"
        if shape_path.exists():
            per_match = json.loads(shape_path.read_text())
            if coach["games"] < 5:  # small sample: one map per game
                groups = [
                    (f"vs {r.opponent}, {r.date} ({r.formation})", [per_match[str(r.match_id)]])
                    for r in subj.itertuples()
                ]
            else:  # season: one map for the most-used starting formation
                top = subj.formation.astype(str).mode()[0]
                ids = subj[subj.formation.astype(str) == top].match_id
                groups = [(f"{len(ids)} games starting in {top}", [per_match[str(i)] for i in ids])]
            coach["shapes"] = []
            for label, matches in groups:
                passes = [tuple(r) for m in matches for r in m]
                shape = average_shape(passes, min_passes=max(5, 3 * len(matches)))
                coach["shapes"].append(
                    {"label": label, "positions": {p: [round(float(x), 1), round(float(y), 1)] for p, (x, y) in shape.items()}}
                )
        out["coaches"].append(coach)
    OUT.mkdir(exist_ok=True)
    (OUT / "fingerprint.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    pd.DataFrame(rows).to_csv(OUT / "fingerprint.csv", index=False)
    return out


if __name__ == "__main__":
    res = build()
    for c in res["coaches"]:
        print(f"\n{c['coach']} ({c['sample']})")
        for k, v in c["values"].items():
            print(f"  {k:30s} {v['value']:8.2f}  median {v['baseline_median']:8.2f}  pct {v['percentile']:5.1f}  rank {v['rank']}/{v['of']}")
        print("  formations:", c.get("formations"))
        for sh in c["shapes"]:
            print("  shape", sh["label"], sh["positions"])
