"""Download StatsBomb open data and compute one row of metrics per team per match.

    python -m coach_fingerprint.pipeline            # all contexts
    python -m coach_fingerprint.pipeline emery      # one context
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from . import metrics as M
from . import statsbomb as sb
from .coaches import CONTEXTS, Context

DATA = Path(__file__).resolve().parents[2] / "data"


def _process_match(ctx: Context, match: dict) -> tuple[list[dict], dict]:
    ev = sb.events(match["match_id"])
    frames = sb.frames_360(match["match_id"]) if ctx.use_360 else None
    rows, shapes = [], {}
    for side, other in (("home", "away"), ("away", "home")):
        team = match[f"{side}_team"]
        tid, tname = team[f"{side}_team_id"], team[f"{side}_team_name"]
        row = {
            "context": ctx.key,
            "match_id": match["match_id"],
            "date": match["match_date"],
            "team": tname,
            "opponent": match[f"{other}_team"][f"{other}_team_name"],
            "venue": side,
            "goals_for": match[f"{side}_score"],
            "goals_against": match[f"{other}_score"],
            "manager": ", ".join(sb.managers(match, side)),
            "formation": next(
                (str(e["tactics"]["formation"]) for e in ev
                 if e["type"]["name"] == "Starting XI" and e["team"]["id"] == tid), ""),
            **M.team_match_metrics(ev, tid),
        }
        if frames:
            row.update(M.press_frames_360(frames, ev, tid))
        rows.append(row)
        shapes[tname] = M.build_up_positions(ev, tid)
    return rows, shapes


def run_context(ctx: Context, workers: int = 8) -> pd.DataFrame:
    if ctx.competition_id is None:
        print(f"[{ctx.key}] no data source: {ctx.sample}")
        return pd.DataFrame()
    matches = sb.matches(ctx.competition_id, ctx.season_id)
    print(f"[{ctx.key}] {len(matches)} matches")
    rows: list[dict] = []
    subject_shapes: dict[int, list] = {}
    with ThreadPoolExecutor(workers) as pool:
        for i, (r, shapes) in enumerate(pool.map(lambda m: _process_match(ctx, m), matches), 1):
            rows.extend(r)
            if ctx.team in shapes:
                subject_shapes[r[0]["match_id"]] = shapes[ctx.team]
            if i % 25 == 0:
                print(f"  {i}/{len(matches)}")
    df = pd.DataFrame(rows)
    df["is_subject"] = (df.team == ctx.team) & df.manager.str.contains(ctx.manager_match)
    df["in_baseline"] = ~df.team.isin(ctx.exclude_from_baseline)
    keep = set(df.loc[df.is_subject, "match_id"])
    shapes_out = {str(k): v for k, v in subject_shapes.items() if k in keep}
    (DATA / f"shapes_{ctx.key}.json").write_text(json.dumps(shapes_out))
    return df


def main(keys: list[str]) -> None:
    DATA.mkdir(exist_ok=True)
    for ctx in CONTEXTS:
        if keys and ctx.key not in keys:
            continue
        df = run_context(ctx)
        if not df.empty:
            df.to_csv(DATA / f"team_matches_{ctx.key}.csv", index=False)
            print(f"[{ctx.key}] wrote {len(df)} rows")


if __name__ == "__main__":
    main(sys.argv[1:])
