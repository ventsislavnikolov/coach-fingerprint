"""Which free data covers which coach, and what each coach is compared against.

Checked against StatsBomb open data on 2026-11-16. None of the three coaches is
covered in his current job, so each 'context' says what the sample really is.
"""

from dataclasses import dataclass, field


@dataclass
class Context:
    key: str
    coach: str
    team: str
    competition_id: int | None
    season_id: int | None
    sample: str
    baseline: str
    # Teams left out of the baseline (e.g. the one club every match involves).
    exclude_from_baseline: list[str] = field(default_factory=list)
    manager_match: str = ""
    use_360: bool = False


CONTEXTS = [
    Context(
        key="hoeness",
        coach="Sebastian Hoeneß",
        team="VfB Stuttgart",
        competition_id=9,
        season_id=281,
        sample="Stuttgart's 2 Bundesliga games vs Leverkusen, 2023/24",
        baseline="the 16 other Bundesliga teams, in their games vs Leverkusen",
        exclude_from_baseline=["Bayer Leverkusen"],
        manager_match="Hoene",
        use_360=True,
    ),
    Context(
        key="emery",
        coach="Unai Emery",
        team="Sevilla",
        competition_id=11,
        season_id=27,
        sample="Sevilla's full La Liga season, 2015/16 (38 games)",
        baseline="all 20 La Liga teams, 2015/16",
        manager_match="Emery",
    ),
    Context(
        key="farioli",
        coach="Francesco Farioli",
        team="FC Porto",
        competition_id=None,
        season_id=None,
        sample="No free event data (StatsBomb open data has no Farioli match)",
        baseline="n/a",
    ),
]
