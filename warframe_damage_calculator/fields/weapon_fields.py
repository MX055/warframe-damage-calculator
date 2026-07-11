from typing import TypedDict

from ..models import dist


class WeaponFields(TypedDict, total=False):
    name: str | None
    type: str | None
    damage_dist: dist
    forced_procs: dist
    crit_chance: float
    crit_damage: float
    status_chance: float