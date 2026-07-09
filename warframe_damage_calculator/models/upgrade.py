from __future__ import annotations

from dataclasses import dataclass, field

from .dist import dist


@dataclass(eq=False)
class Upgrade:
    """Represents a single upgrade that can modify weapon stats.

    Use this for one mod, arcane, buff, or similar effect. Each field is a
    possible bonus, such as base damage, critical chance, status chance,
    multishot, or a weapon-specific effect.

    Most upgrades only use a few fields. Any field left at its default value
    has no effect.

    ``Build`` combines multiple ``Upgrade`` objects before they are applied
    to a weapon.
    """
    name: str | None = None
    category: str = "upgrade"
    damage_dist: dist = field(default_factory=dist)
    multiplicative_base_damage: float = 0.0
    base_damage: float = 0.0
    faction_damage: float = 0.0
    weakpoint_damage: float = 0.0
    attack_speed: float = 0.0
    multiplicative_fire_rate: float = 0.0
    fire_rate: float = 0.0
    reload_speed: float = 0.0
    magazine_capacity: float = 0.0
    ammo_efficiency: float = 0.0
    multishot: float = 0.0
    flat_crit_chance: float = 0.0
    multiplicative_crit_chance: float = 0.0
    crit_chance: float = 0.0
    multiplicative_weakpoint_crit_chance: float = 0.0
    weakpoint_crit_chance: float = 0.0
    flat_crit_damage: float = 0.0
    crit_damage: float = 0.0
    status_chance: float = 0.0
    status_damage: float = 0.0
    hunter_munitions: float = 0.0
    internal_bleeding: float = 0.0
    primed_chamber: float = 0.0
    vigilante_bonus: float = 0.0
    secondary_enervate: int = 0
    secondary_encumber: float = 0.0
    melee_duplicate: float = 0.0
    melee_doughty: float = 0.0
    fire_rate_lock: bool = False
    multishot_lock: bool = False