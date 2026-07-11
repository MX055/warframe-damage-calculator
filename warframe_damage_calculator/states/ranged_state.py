from dataclasses import dataclass, field

from ..models.dist import dist
from .weapon_state import WeaponState


@dataclass
class RangedState(WeaponState):
    trigger: str | None = None
    is_beam: bool = False
    is_battery: bool = False
    explosion_damage_dist: dist = field(default_factory=dist)
    explosion_forced_procs: dist = field(default_factory=dist)
    explosion_total_damage: float = 0.0
    multishot: float = 1.0
    multiplicative_fire_rate: float = 1.0
    fire_rate: float = 0.05
    burst_count: int = 1
    burst_delay: float = 0.0
    charge_time: float = 0.0
    reload_speed: float = 0.0
    recharge_rate: float = 0.0
    ammo_efficiency: float = 0.0
    magazine_capacity: int = 1
    weakpoint_damage: float = 3.0
    multiplicative_weakpoint_crit_chance: float = 1.0
    weakpoint_crit_chance: float = 0.0
    internal_bleeding: float = 0.0