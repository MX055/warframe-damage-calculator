from ..models.dist import dist
from .weapon_field import WeaponField


class RangedField(WeaponField):
    is_beam: bool
    is_battery: bool
    explosion_damage_dist: dist
    explosion_forced_procs: dist
    multishot: float
    fire_rate: float
    burst_count: int
    burst_delay: float
    charge_time: float
    reload_speed: float
    recharge_rate: float
    magazine_capacity: int
    weakpoint_damage: float