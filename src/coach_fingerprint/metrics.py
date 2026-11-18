"""Per-team, per-match metrics computed from StatsBomb event data.

StatsBomb pitch: 120 x 80 units. Every event's location is given from the
acting team's point of view, attacking left to right (own goal at x=0).
Distances reported to the user are converted to metres on a 105 x 68 pitch.

Each metric maps to a claim made in the TacticalPathway threads; see README.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

X_M = 105 / 120
Y_M = 68 / 80

FULL_BACKS = {"Left Back", "Right Back", "Left Wing Back", "Right Wing Back"}
CENTRE_BACKS = {"Center Back", "Left Center Back", "Right Center Back"}
TOUCH_TYPES = {"Pass", "Ball Receipt*", "Carry", "Dribble", "Shot", "Dispossessed", "Miscontrol"}
DEF_ACTIONS = {"Interception", "Clearance", "Block", "Ball Recovery", "Pressure"}
SET_PIECE_PATTERNS = {"From Corner", "From Free Kick", "From Throw In", "From Kick Off", "From Goal Kick"}


def _secs(ev: dict) -> float:
    h, m, s = ev["timestamp"].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _is_tackle(ev: dict) -> bool:
    return ev["type"]["name"] == "Duel" and ev.get("duel", {}).get("type", {}).get("name") == "Tackle"


def _ppda_action(ev: dict) -> bool:
    # Standard PPDA defensive actions: tackles, interceptions, fouls.
    t = ev["type"]["name"]
    return _is_tackle(ev) or t in {"Interception", "Foul Committed"}


def _is_def_action(ev: dict) -> bool:
    return ev["type"]["name"] in DEF_ACTIONS or _is_tackle(ev)


def team_match_metrics(events: list[dict], team_id: int) -> dict:
    own = [e for e in events if e.get("team", {}).get("id") == team_id]
    opp = [e for e in events if e.get("team", {}).get("id") not in (None, team_id)]

    # ---- Pressing ---------------------------------------------------------
    opp_passes_own60 = sum(
        1 for e in opp if e["type"]["name"] == "Pass" and "location" in e and e["location"][0] < 72
    )
    def_actions_opp60 = sum(1 for e in own if _ppda_action(e) and "location" in e and e["location"][0] > 48)
    pressures = [e["location"][0] for e in own if e["type"]["name"] == "Pressure" and "location" in e]

    # ---- Defensive line proxy: where centre-backs make defensive actions ---
    cb_def_x = [
        e["location"][0]
        for e in own
        if _is_def_action(e) and e.get("position", {}).get("name") in CENTRE_BACKS and "location" in e
    ]

    # ---- Full-back touches (Opta-style height/width) -----------------------
    fb = [
        e["location"]
        for e in own
        if e["type"]["name"] in TOUCH_TYPES and e.get("position", {}).get("name") in FULL_BACKS and "location" in e
    ]
    fb_mid = [loc for loc in fb if 40 <= loc[0] <= 80]

    # ---- Holding midfielder dropping into the back line in build-up ------
    # Share of a defensive midfielder's own-half open-play passes played from
    # the centre-backs' zone (first 26 m), i.e. the '6 drops in' pattern.
    dm_passes = [
        e["location"]
        for e in own
        if e["type"]["name"] == "Pass"
        and "Defensive Midfield" in e.get("position", {}).get("name", "")
        and "location" in e
        and e["location"][0] < 60
        and not e.get("pass", {}).get("type")
        and e["play_pattern"]["name"] in {"Regular Play", "From Goal Kick", "From Keeper"}
    ]

    # ---- Counter-press ----------------------------------------------------
    counterpress_actions = sum(1 for e in own if e.get("counterpress"))
    turnovers, regains = _counterpress_regains(events, team_id)

    # ---- Space behind: what the opponent creates in transition -------------
    opp_shots = [e for e in opp if e["type"]["name"] == "Shot" and e["play_pattern"]["name"] != "Other"]
    by_id = {e["id"]: e for e in events}

    def _through_ball(shot: dict) -> bool:
        kp = by_id.get(shot.get("shot", {}).get("key_pass_id"))
        if not kp:
            return False
        p = kp.get("pass", {})
        return bool(p.get("through_ball")) or p.get("technique", {}).get("name") == "Through Ball"

    xg = lambda s: s.get("shot", {}).get("statsbomb_xg", 0.0) or 0.0  # noqa: E731
    counter_shots = [s for s in opp_shots if s["play_pattern"]["name"] == "From Counter"]
    tb_shots = [s for s in opp_shots if _through_ball(s)]

    # ---- Context: possession by pass share --------------------------------
    own_passes = sum(1 for e in own if e["type"]["name"] == "Pass")
    opp_passes = sum(1 for e in opp if e["type"]["name"] == "Pass")

    return {
        "ppda": opp_passes_own60 / def_actions_opp60 if def_actions_opp60 else np.nan,
        "press_height_m": np.mean(pressures) * X_M if pressures else np.nan,
        "high_press_share": np.mean([x >= 80 for x in pressures]) if pressures else np.nan,
        "pressures": len(pressures),
        "cb_action_height_m": np.mean(cb_def_x) * X_M if cb_def_x else np.nan,
        "fb_touch_height_m": np.mean([l[0] for l in fb]) * X_M if fb else np.nan,
        "fb_touch_width_m": np.mean([abs(l[1] - 40) for l in fb]) * Y_M if fb else np.nan,
        "fb_central_share": np.mean([abs(l[1] - 40) < 22 for l in fb_mid]) if fb_mid else np.nan,
        "fb_touches": len(fb),
        "dm_drop_share": np.mean([loc[0] <= 30 for loc in dm_passes]) if dm_passes else np.nan,
        "counterpress_actions": counterpress_actions,
        "open_play_losses": turnovers,
        "regains_5s": regains,
        "regain_5s_rate": regains / turnovers if turnovers else np.nan,
        "xg_conceded": sum(xg(s) for s in opp_shots),
        "counter_shots_conceded": len(counter_shots),
        "counter_xg_conceded": sum(xg(s) for s in counter_shots),
        "through_ball_shots_conceded": len(tb_shots),
        "through_ball_xg_conceded": sum(xg(s) for s in tb_shots),
        "possession": own_passes / (own_passes + opp_passes) if own_passes + opp_passes else np.nan,
    }


WON = {"Won", "Success", "Success In Play", "Success To Team"}


def _is_loss(ev: dict) -> bool:
    t = ev["type"]["name"]
    if t in {"Dispossessed", "Miscontrol"}:
        return True
    if t == "Pass":
        return ev.get("pass", {}).get("outcome", {}).get("name") == "Incomplete"
    if t == "Dribble":
        return ev.get("dribble", {}).get("outcome", {}).get("name") == "Incomplete"
    return False


def _is_regain(ev: dict) -> bool:
    t = ev["type"]["name"]
    if t == "Ball Recovery":
        return not ev.get("ball_recovery", {}).get("recovery_failure")
    if t == "Interception":
        return ev.get("interception", {}).get("outcome", {}).get("name") in WON
    if _is_tackle(ev):
        return ev.get("duel", {}).get("outcome", {}).get("name") in WON
    return False


def _counterpress_regains(events: list[dict], team_id: int, window: float = 5.0) -> tuple[int, int]:
    """Open-play ball losses by `team_id`, and how many it won back within `window` seconds.

    A loss is an incomplete open-play pass, a failed dribble, a miscontrol or
    being dispossessed. A regain is a won ball recovery, interception or tackle
    by the same team within `window` seconds, after the opponent has touched
    the ball, with no stoppage in between.
    """
    stop = {"Half End", "Foul Committed", "Injury Stoppage", "Substitution", "Offside"}
    losses = regains = 0
    n = len(events)
    for i, e in enumerate(events):
        if e.get("team", {}).get("id") != team_id or not _is_loss(e):
            continue
        if e["play_pattern"]["name"] not in {"Regular Play", "From Counter", "From Keeper", "From Goal Kick"}:
            continue
        losses += 1
        t0, period, opp_touched = _secs(e), e["period"], False
        for f in events[i + 1 : n]:
            if f["period"] != period or _secs(f) - t0 > window or f["type"]["name"] in stop:
                break
            if f.get("team", {}).get("id") == team_id:
                if opp_touched and _is_regain(f):
                    regains += 1
                    break
            elif "location" in f and f["type"]["name"] != "Pressure":
                opp_touched = True
    return losses, regains


def build_up_positions(events: list[dict], team_id: int) -> list[tuple[str, float, float]]:
    """(position, x, y) of every pass the team plays in its own half in open play.

    Averaged by position over many matches, this gives a build-up shape map.
    """
    out = []
    for e in events:
        if (
            e.get("team", {}).get("id") == team_id
            and e["type"]["name"] == "Pass"
            and "location" in e
            and e["location"][0] < 60
            and e["play_pattern"]["name"] in {"Regular Play", "From Goal Kick", "From Keeper"}
            and "position" in e
            and not e.get("pass", {}).get("type")  # skip restarts (goal kicks, throw-ins...)
        ):
            out.append((e["position"]["name"], e["location"][0], e["location"][1]))
    return out


def press_frames_360(frames: list[dict], events: list[dict], team_id: int) -> dict:
    """360-based extras: how many players press high, and the back-line height.

    For each opponent pass from its own third, count visible defending outfield
    players in that third (pressing commitment). For opponent passes in the
    middle third, the defending back line is the mean of the two deepest
    defending outfield players visible, as metres from the defending goal.
    """
    by_id = {e["id"]: e for e in events}
    commit, line = [], []
    for fr in frames or []:
        ev = by_id.get(fr["event_uuid"])
        if not ev or ev["type"]["name"] != "Pass" or ev.get("team", {}).get("id") == team_id:
            continue
        if ev["play_pattern"]["name"] in {"From Corner", "From Free Kick", "From Throw In"}:
            continue
        defenders = [p["location"] for p in fr["freeze_frame"] if not p["teammate"] and not p["keeper"]]
        x = ev["location"][0]
        if x < 40:
            commit.append(sum(1 for d in defenders if d[0] < 40))
        elif x <= 80 and len(defenders) >= 6:
            deepest = sorted(d[0] for d in defenders)[-2:]
            line.append((120 - np.mean(deepest)) * X_M)
    return {
        "press_commit_360": np.mean(commit) if commit else np.nan,
        "line_height_360_m": np.mean(line) if line else np.nan,
    }


def average_shape(rows: list[tuple[str, float, float]], min_passes: int = 30) -> dict[str, tuple[float, float]]:
    acc: dict[str, list] = defaultdict(list)
    for pos, x, y in rows:
        acc[pos].append((x, y))
    return {p: tuple(np.mean(v, axis=0)) for p, v in acc.items() if len(v) >= min_passes}
