from dataclasses import dataclass, field

from .dist import Dist

@dataclass
class WeaponState:
    damage_dist: Dist = field(default_factory=Dist)
    forced_procs: Dist = field(default_factory=Dist)
    total_damage: float = 0.0
    multiplicative_base_damage: float = 1.0
    base_damage: float = 1.0
    faction_damage: float = 1.0
    flat_crit_chance: float = 0.0
    multiplicative_crit_chance: float = 1.0
    crit_chance: float = 0.0
    flat_crit_damage: float = 0.0
    crit_damage: float = 0.0
    status_chance: float = 0.0
    status_damage: float = 1.0

@dataclass
class MeleeState(WeaponState):
    attack_speed: float = 1.0
    melee_duplicate: float = 0.0

@dataclass
class RangedState(WeaponState):
    explosion_damage_dist: Dist = field(default_factory=Dist)
    explosion_forced_procs: Dist = field(default_factory=Dist)
    explosion_total_damage: float = 0.0
    weakpoint_damage: float = 3.0
    multiplicative_fire_rate: float = 1.0
    fire_rate: float = 0.0
    charge_time: float = 0.0
    reload_speed: float = 0.0
    magazine_capacity: int = 0
    multishot: float = 0.0
    is_beam: bool = False
    multiplicative_weakpoint_crit_chance: float = 1.0
    weakpoint_crit_chance: float = 0.0
    internal_bleeding: float = 0.0

@dataclass
class PrimaryState(RangedState):
    hunter_munitions: float = 0.0
    primed_chamber: float = 0.0
    vigilante_bonus: float = 0.0

@dataclass
class SecondaryState(RangedState):
    secondary_enervate: int = 0