from dataclasses import dataclass

from ..damage import Dist


@dataclass(frozen=True, slots=True)
class DamageMetrics:
    direct_dph: float
    dot_dph: float
    total_dph: float
    direct_dps: float
    dot_dps: float
    total_dps: float


@dataclass(frozen=True, slots=True)
class DamageResult(DamageMetrics):
    pass


@dataclass(frozen=True, slots=True)
class AverageResult:
    damage: Dist
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float
    magazine_capacity: float
    reload_time: float
    ammo_cost: float
    ammo_efficiency: float
    punch_through: float
    burst_count: float
    burst_delay: float
    charge_time: float
    attack_speed: float
    heavy_attack_speed: float
    heavy_attack_efficiency: float
    initial_combo: float
    direct_dph: float
    dot_dph: float
    total_dph: float
    direct_dps: float
    dot_dps: float
    total_dps: float
    crit_multiplier: float
    weakpoint_crit_chance: float
    weakpoint_crit_multiplier: float
    attack_rate: float
    first_shot_damage_multiplier: float
    combo_multiplier: float
    melee_doughty_bonus: float
    crit_tier_bonus: float
    weakpoint_crit_tier_bonus: float
    secondary_enervate_bonus: float
    weakpoint_secondary_enervate_bonus: float
    falloff_multiplier: float
