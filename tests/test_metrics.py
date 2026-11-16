from coach_fingerprint import metrics as M

A, B = 1, 2


def ev(i, team, typ, loc=None, t="00:00:00.000", period=1, pattern="Regular Play", **extra):
    e = {
        "id": f"e{i}", "index": i, "period": period, "timestamp": t,
        "type": {"name": typ}, "team": {"id": team}, "possession": 1,
        "possession_team": {"id": team}, "play_pattern": {"name": pattern},
    }
    if loc:
        e["location"] = loc
    e.update(extra)
    return e


def test_ppda_counts_opponent_passes_in_own_60_and_actions_in_attacking_60():
    events = [
        ev(1, B, "Pass", [30, 40]),
        ev(2, B, "Pass", [70, 40]),
        ev(3, B, "Pass", [100, 40]),  # outside B's own 60%: ignored
        ev(4, A, "Interception", [90, 40]),
        ev(5, A, "Interception", [20, 40]),  # deep: ignored
    ]
    assert M.team_match_metrics(events, A)["ppda"] == 2


def test_counterpress_regain_needs_opponent_touch_within_window():
    loss = {"pass": {"outcome": {"name": "Incomplete"}}}
    events = [
        ev(1, A, "Pass", [60, 40], "00:01:00.000", **loss),
        ev(2, B, "Ball Recovery", [60, 40], "00:01:01.000"),
        ev(3, A, "Ball Recovery", [58, 40], "00:01:03.000"),
        ev(4, A, "Pass", [60, 40], "00:02:00.000", **loss),
        ev(5, B, "Ball Recovery", [60, 40], "00:02:01.000"),
        ev(6, A, "Ball Recovery", [58, 40], "00:02:09.000"),  # too late
    ]
    assert M._counterpress_regains(events, A) == (2, 1)


def test_full_back_width_and_central_share():
    fb = {"position": {"name": "Left Back"}}
    events = [ev(1, A, "Pass", [60, 40], **fb), ev(2, A, "Pass", [60, 0], **fb)]
    m = M.team_match_metrics(events, A)
    assert m["fb_central_share"] == 0.5
    assert abs(m["fb_touch_width_m"] - 20 * 68 / 80) < 1e-9
