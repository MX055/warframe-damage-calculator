from typing import TypedDict

from ..models import dist


class WeaponFields(TypedDict):
    """Keyword fields shared by every weapon.

    These are the basic values needed to create a weapon: its damage
    distribution, forced status procs, critical chance, critical damage, and
    status chance.

    ``damage_dist`` and ``forced_procs`` use ``dist`` because they contain
    values for multiple damage types. The remaining fields are scalar stats.

    Ranged and melee field classes extend this set with weapon-family inputs.
    """
    damage_dist: dist
    forced_procs: dist
    crit_chance: float
    crit_damage: float
    status_chance: float