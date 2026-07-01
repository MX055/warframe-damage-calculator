from __future__ import annotations

from dataclasses import dataclass

from ..mechanics import dist


@dataclass
class Upgrade:
    damage_dist: dist = dist()
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
    melee_duplicate: float = 0.0
    melee_doughty: float = 0.0
    fire_rate_lock: bool = False
    multishot_lock: bool = False