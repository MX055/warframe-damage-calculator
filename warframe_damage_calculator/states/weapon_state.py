from dataclasses import dataclass, field

from ..models.dist import dist


@dataclass
class WeaponState:
    name: str | None = None
    type: str | None = None
    damage: dist = field(default_factory=dist)
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
