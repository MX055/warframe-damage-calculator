from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.damage import Dist
from ...domain.status import StatusModel
from ...domain.upgrades import ResolvedEffect
from ...domain.weapons import Attack
from .stats import BaseAttackStats, EffectiveAttackStats, ModdedAttackStats, ResolvedStats, Stats


@dataclass(slots=True)
class ResolvedAttackMetrics:
    damage: Dist = field(default_factory=Dist)
    crit_chance: float = 0
    crit_damage: float = 1
    status_chance: float = 0
    status_duration: float = 0
    multishot: float = 1
    fire_rate: float = 0
    magazine_capacity: float = 0
    reload_time: float = 0
    ammo_cost: float = 0
    ammo_efficiency: float = 0
    punch_through: float = 0
    accuracy: float = 0
    recoil: float = 0
    burst_count: float = 1
    burst_delay: float = 0
    charge_time: float = 0
    attack_speed: float = 0
    heavy_attack_speed: float = 1
    heavy_attack_efficiency: float = 0
    initial_combo: float = 0
    crit_multiplier: float = 1
    weak_point_crit_chance: float = 0
    weak_point_crit_multiplier: float = 1
    attack_rate: float = 0
    procs_per_shot: float = 0
    flat_dph: float | None = None
    flat_dps: float | None = None
    flat_dotph: float | None = None
    flat_dotps: float | None = None
    total_dph: float | None = None
    total_dps: float | None = None
    first_shot_damage_multiplier: float = 1
    combo_multiplier: float = 1
    puncture_status_crit_damage_bonus: float = 0
    crit_tier_bonus: float = 0
    weak_point_crit_tier_bonus: float = 0
    secondary_enervate_bonus: float = 0
    weak_point_secondary_enervate_bonus: float = 0
    falloff_multiplier: float = 1


@dataclass(slots=True)
class SpatialMetrics:
    falloff_multiplier: float | None = None
    damage_mass: float | None = None
    dimension: int | None = None
    flat_dph: float | None = None
    flat_dotph: float | None = None
    total_dph: float | None = None
    flat_dps: float | None = None
    flat_dotps: float | None = None
    total_dps: float | None = None


@dataclass(slots=True)
class PreliminaryAttack:
    provisional: Stats
    status_model: StatusModel
    damage: Dist
    forced_procs: Dist
    status_chance: float
    multishot: float
    attack_rate: float
    status_duration: float
    special_effects: tuple[ResolvedEffect, ...]
    crit_chance: float
    trigger_crit_chance: float


@dataclass(slots=True)
class ResolvedAttack:
    attack: Attack
    base: BaseAttackStats
    modded: ModdedAttackStats
    effective: EffectiveAttackStats
    upgrades: ResolvedStats
    evolutions: ResolvedStats
    average: ResolvedAttackMetrics
    spatial: SpatialMetrics
    status_effects: dict[str, float] = field(default_factory=dict)
    generated_by: str | None = None
    generated_from: str | None = None
