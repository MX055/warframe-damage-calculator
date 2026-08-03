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
class AttackDamageMetrics(DamageMetrics):
    damage: Dist
    first_shot_damage_multiplier: float
    combo_multiplier: float


@dataclass(frozen=True, slots=True)
class AttackCriticalMetrics:
    crit_chance: float
    crit_damage: float
    crit_multiplier: float
    crit_tier_bonus: float
    puncture_status_crit_damage_bonus: float
    secondary_enervate_bonus: float
    weak_point_crit_chance: float
    weak_point_crit_multiplier: float
    weak_point_crit_tier_bonus: float
    weak_point_secondary_enervate_bonus: float


@dataclass(frozen=True, slots=True)
class AttackTimingMetrics:
    fire_rate: float
    attack_speed: float
    attack_rate: float
    multishot: float
    magazine_capacity: float
    reload_time: float
    ammo_cost: float
    ammo_efficiency: float
    burst_count: float
    burst_delay: float
    charge_time: float
    heavy_attack_speed: float
    heavy_attack_efficiency: float
    initial_combo: float
