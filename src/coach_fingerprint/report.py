"""Render output/index.html: a self-contained fingerprint page built from output/fingerprint.json.

    python -m coach_fingerprint.report
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output"
TEMPLATE = Path(__file__).with_name("report_template.html")

# Claims from the TacticalPathway threads, as testable statements. Each claim is
# scored by the average percentile of the metrics listed (direction already
# folded into the percentile, so high always means 'more of the claim').
CLAIMS = [
    {"claim": "Presses high and aggressively", "metrics": ["ppda", "press_height_m", "high_press_share", "press_commit_360"]},
    {"claim": "Holds a high defensive line", "metrics": ["cb_action_height_m", "line_height_360_m"]},
    {"claim": "Holding midfielder drops into the back line", "metrics": ["dm_drop_share"]},
    {"claim": "Full-backs push high up the pitch", "metrics": ["fb_touch_height_m"]},
    {"claim": "Full-backs invert into central areas", "metrics": ["fb_touch_width_m", "fb_central_share"]},
    {"claim": "Counter-presses straight after losing the ball", "metrics": ["counterpress_actions", "regain_5s_rate"]},
    {"claim": "Leaves space in behind (concedes in transition)", "metrics": ["counter_xg_conceded", "through_ball_shots_conceded"]},
]


def verdicts(fp: dict) -> list[dict]:
    rows = []
    for c in CLAIMS:
        row = {"claim": c["claim"], "metrics": c["metrics"], "coaches": {}}
        for coach in fp["coaches"]:
            pcts = [coach["values"][k]["percentile"] for k in c["metrics"] if k in coach["values"]]
            if not pcts:
                row["coaches"][coach["key"]] = {"score": None, "verdict": "No data"}
                continue
            score = sum(pcts) / len(pcts)
            verdict = "Supported" if score >= 67 else "Not supported" if score <= 33 else "Mixed"
            row["coaches"][coach["key"]] = {"score": round(score), "verdict": verdict}
        rows.append(row)
    return rows


def main() -> None:
    fp = json.loads((OUT / "fingerprint.json").read_text())
    fp["claims"] = verdicts(fp)
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", json.dumps(fp, ensure_ascii=False))
    (OUT / "index.html").write_text(html)
    print(f"wrote {OUT / 'index.html'}")


if __name__ == "__main__":
    main()
