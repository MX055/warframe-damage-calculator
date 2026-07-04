from typing import TypedDict

from ..models.dist import dist


class WeaponField(TypedDict, total=True):
    damage_dist: dist
    forced_procs: dist
    crit_chance: float
    crit_damage: float
    status_chance: float