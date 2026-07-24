from collections.abc import Mapping

from ..models.data import Data
from ..models.dist import Dist
from ..utils.types import JsonValue, Number


class GlobalWeaponStats(Data):
    reload_time: Number = 0.0
    magazine_size: Number = 1
    recharge_rate: Number = 0.0
    incarnon_charges: Number = 0
    incarnon_recharge_count: Number = 0
    disposition: Number = 0.0
    is_incarnon: bool = False
    is_progenitor: bool = False
    is_battery: bool = False


class AttackStats(Data):
    ammo_cost: Number = 1
    punch_through: Number | str = 0.0
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    falloff: Mapping[str, JsonValue] = {}
    crit_chance: Number = 0.0
    crit_damage: Number = 1.0
    status_chance: Number = 0.0
    multishot: Number = 1.0
    fire_rate: Number = 0.05
    burst_count: int = 1
    burst_delay: Number = 0.0
    charge_time: Number = 0.0
    co_factor: Number = 1.0
    co_effect: str = "adds"
    range: Number = 0.0
    damage_bonus: Number = 0.0
    initial_combo: Number = 0.0
    heavy_attack_efficiency: Number = 0.0


class WeaponStats(Data):
    ammo_cost: Number = 1
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    punch_through: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 1.0
    status_chance: Number = 0.0
    status_duration: Number = 6.0


class RangedStats(WeaponStats):
    burst_count: int = 1
    burst_delay: Number = 0.0
    charge_time: Number = 0.0
    fire_rate: Number = 0.05
    start_range: Number
    end_range: Number
    final_multiplier: Number
    magazine_capacity: Number = 1
    multishot: Number = 1.0
    recharge_rate: Number = 0.0
    reload_speed: Number = 0.0
    weakpoint_damage: Number = 3.0
    projectile_speed: Number = 0.0
    range: Number = 0.0


class MeleeStats(WeaponStats):
    attack_speed: Number = 1.0
    range: Number = 0.0


class PrimaryStats(RangedStats):
    pass


class SecondaryStats(RangedStats):
    pass
