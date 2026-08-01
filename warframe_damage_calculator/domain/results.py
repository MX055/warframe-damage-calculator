from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .damage import Dist
from .enemies import Enemy
from .loadouts import Loadout
from .status import StatusModel
from .upgrades import ResolvedEffect
from .weapons import Attack, Weapon


class Stats(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try: return self[name]
        except KeyError: raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class BaseAttackStats(Stats):
    damage: Dist
    forced_procs: Dist
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float


class ModdedAttackStats(Stats):
    damage: Dist
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float


class EffectiveAttackStats(ModdedAttackStats):
    dot_base_damage: float
    dot_elemental_bonuses: Stats
    forced_procs: Dist
    status_model: StatusModel
    attack_event_rate: float
    reload_time: float
    faction_damage: float
    target_vulnerability: float
    overguard_damage_multiplier: float
    non_crit_bonus_damage: float
    non_crit_bonus_chance: float
    weakpoint_damage_bonus: float
    special_effects: tuple[ResolvedEffect, ...]


@dataclass(slots=True)
class ResolvedStats:
    proportional: Stats = field(default_factory=Stats)
    base: Stats = field(default_factory=Stats)
    flat: Stats = field(default_factory=Stats)
    families: dict[str, Stats] = field(default_factory=dict)
    maximums: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContributionResult:
    shapley: dict[str, float]
    removal: dict[str, float]
    evaluations: int
    samples: int


@dataclass(frozen=True, slots=True)
class DamageMetrics:
    direct_dph: float
    dot_dph: float
    total_dph: float
    direct_dps: float
    dot_dps: float
    total_dps: float


def _damage_metrics(source: object) -> DamageMetrics | None:
    direct_dph = getattr(source, "flat_dph")
    dot_dph = getattr(source, "flat_dotph")
    total_dph = getattr(source, "total_dph")
    direct_dps = getattr(source, "flat_dps")
    dot_dps = getattr(source, "flat_dotps")
    total_dps = getattr(source, "total_dps")
    if all(value is None for value in (direct_dph, dot_dph, total_dph, direct_dps, dot_dps, total_dps)): return None
    return DamageMetrics(float(direct_dph or 0), float(dot_dph or 0), float(total_dph or 0), float(direct_dps or 0), float(dot_dps or 0), float(total_dps or 0))


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
    melee_duplicate_multiplier: float
    melee_doughty_bonus: float
    crit_tier_bonus: float
    weakpoint_crit_tier_bonus: float
    secondary_enervate_bonus: float
    weakpoint_secondary_enervate_bonus: float
    falloff_multiplier: float


@dataclass(slots=True)
class AverageAttackStats:
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
    burst_count: float = 1
    burst_delay: float = 0
    charge_time: float = 0
    attack_speed: float = 0
    heavy_attack_speed: float = 1
    heavy_attack_efficiency: float = 0
    initial_combo: float = 0
    crit_multiplier: float = 1
    weakpoint_crit_chance: float = 0
    weakpoint_crit_multiplier: float = 1
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
    melee_duplicate_multiplier: float = 1
    melee_doughty_bonus: float = 0
    crit_tier_bonus: float = 0
    weakpoint_crit_tier_bonus: float = 0
    secondary_enervate_bonus: float = 0
    weakpoint_secondary_enervate_bonus: float = 0
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
class AttackResult:
    attack: Attack
    base: BaseAttackStats
    modded: ModdedAttackStats
    effective: EffectiveAttackStats
    upgrades: ResolvedStats
    evolutions: ResolvedStats
    average: AverageResult
    spatial: SpatialMetrics
    status_effects: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StatusResult:
    expected_procs_per_attack: float
    sustained_procs: dict[str, float]
    effects: dict[str, float]


@dataclass(frozen=True, slots=True)
class SpatialDamageMetrics:
    direct_dph_mass: float
    dot_dph_mass: float
    total_dph_mass: float
    direct_dps_mass: float
    dot_dps_mass: float
    total_dps_mass: float


@dataclass(frozen=True, slots=True)
class SpatialResult:
    dimension: int
    falloff_multiplier: float
    damage_mass: float
    direct_dph_mass: float
    dot_dph_mass: float
    total_dph_mass: float
    direct_dps_mass: float
    dot_dps_mass: float
    total_dps_mass: float


@dataclass(frozen=True, slots=True)
class CalculatedAttack:
    base: BaseAttackStats
    modded: ModdedAttackStats
    effective: EffectiveAttackStats
    upgrades: ResolvedStats
    evolutions: ResolvedStats
    average: AverageResult
    status: StatusResult
    spatial: SpatialResult | None


@dataclass(frozen=True, slots=True)
class AggregateResult:
    average: DamageResult
    status: StatusResult


@dataclass(frozen=True, slots=True)
class CalculationResult:
    aggregate: AggregateResult
    attacks: dict[str, CalculatedAttack]
    selected_attack: str
    selected_bodypart: str
    weapon: Weapon
    target: Enemy | None
    loadout: Loadout
    state: dict[str, object]
