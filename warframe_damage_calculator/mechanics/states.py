from dataclasses import dataclass

from .dist import dist


@dataclass
class WeaponState:
    damage_dist: dist = dist()
    forced_procs: dist = dist()
    total_damage: float = 0.0
    multiplicative_base_damage: float = 1.0
    base_damage: float = 1.0
    faction_damage: float = 1.0
    flat_crit_chance: float = 0.0
    multiplicative_crit_chance: float = 1.0
    crit_chance: float = 0.0
    flat_crit_damage: float = 0.0
    crit_damage: float = 1.0
    status_chance: float = 0.0
    status_damage: float = 1.0


@dataclass
class MeleeState(WeaponState):
    attack_speed: float = 1.0
    melee_doughty: float = 0.0
    melee_duplicate: float = 0.0


@dataclass
class RangedState(WeaponState):
    explosion_damage_dist: dist = dist()
    explosion_forced_procs: dist = dist()
    explosion_total_damage: float = 0.0
    weakpoint_damage: float = 3.0
    multiplicative_fire_rate: float = 0.0
    fire_rate: float = 0.0
    charge_time: float = 0.0
    reload_speed: float = 0.0
    magazine_capacity: int = 0
    ammo_efficiency: float = 0.0
    multishot: float = 1.0
    is_beam: bool = False
    multiplicative_weakpoint_crit_chance: float = 0.0
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