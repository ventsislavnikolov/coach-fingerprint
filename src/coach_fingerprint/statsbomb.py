"""Thin loader for StatsBomb open data (https://github.com/statsbomb/open-data).

Files are fetched from GitHub raw and optionally cached on disk. Event files are
large (3-4 MB each), so by default they are not cached: the pipeline reduces a
match to one row of metrics per team and throws the events away.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE_DIR = Path(os.environ.get("COACH_FP_CACHE", Path(__file__).resolve().parents[2] / "data" / "cache"))

_session = requests.Session()


def _get(path: str, cache: bool) -> object:
    local = CACHE_DIR / path
    if local.exists():
        return json.loads(local.read_text())
    for attempt in range(4):
        try:
            r = _session.get(f"{BASE}/{path}", timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
    data = r.json()
    if cache:
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(json.dumps(data))
    return data


def competitions() -> list[dict]:
    return _get("competitions.json", cache=True)


def matches(competition_id: int, season_id: int) -> list[dict]:
    return _get(f"matches/{competition_id}/{season_id}.json", cache=True)


def events(match_id: int, cache: bool = False) -> list[dict]:
    return _get(f"events/{match_id}.json", cache=cache)


def frames_360(match_id: int, cache: bool = False) -> list[dict] | None:
    """360 freeze frames, or None when the match has none."""
    return _get(f"three-sixty/{match_id}.json", cache=cache)


def managers(match: dict, side: str) -> list[str]:
    return [m["name"] for m in (match[f"{side}_team"].get("managers") or [])]
