from dataclasses import dataclass, field

from ..models import dist


@dataclass
class WeaponState:
    """Represents stats shared by every weapon type.

    Calculators use this class to hold the original base stats, the ``moded``
    stats after normal build modifiers, and the final ``effective`` stats used
    for damage output.

    The fields cover common values such as damage, critical chance, critical
    damage, status chance, status damage, and faction damage.

    Specialized state classes add the extra fields needed by ranged, primary,
    secondary, and melee weapons.
    """
    name: str | None = None
    type: str | None = None
    damage_dist: dist = field(default_factory=dist)
    forced_procs: dist = field(default_factory=dist)
    total_damage: float = 0.0
    multiplicative_base_damage: float = 1.0
    base_damage: float = 0.0
    faction_damage: float = 1.0
    flat_crit_chance: float = 0.0
    multiplicative_crit_chance: float = 1.0
    crit_chance: float = 0.0
    flat_crit_damage: float = 0.0
    crit_damage: float = 1.0
    status_chance: float = 0.0
    status_damage: float = 1.0