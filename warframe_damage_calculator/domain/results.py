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


class EffectiveAttackStats(ModdedAttackStats):
    dot_base_damage: float
    dot_elemental_bonuses: Stats
    forced_procs: Dist
    status_model: StatusModel
    instantaneous_fire_rate: float
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
class DamageMetrics:
    direct_dph: float
    dot_dph: float
    total_dph: float
    direct_dps: float
    dot_dps: float
    total_dps: float


def _damage_metrics(source: object, prefix: str = "") -> DamageMetrics | None:
    direct_dph = getattr(source, f"flat_{prefix}dph" if prefix else "flat_dph")
    dot_dph = getattr(source, f"flat_{prefix}dotph" if prefix else "flat_dotph")
    total_dph = getattr(source, f"total_{prefix}dph" if prefix else "total_dph")
    direct_dps = getattr(source, f"flat_{prefix}dps" if prefix else "flat_dps")
    dot_dps = getattr(source, f"flat_{prefix}dotps" if prefix else "flat_dotps")
    total_dps = getattr(source, f"total_{prefix}dps" if prefix else "total_dps")
    if all(value is None for value in (direct_dph, dot_dph, total_dph, direct_dps, dot_dps, total_dps)): return None
    return DamageMetrics(float(direct_dph or 0), float(dot_dph or 0), float(total_dph or 0), float(direct_dps or 0), float(dot_dps or 0), float(total_dps or 0))


class DamagePool:
    @property
    def normal(self) -> DamageMetrics:
        return _damage_metrics(self) or DamageMetrics(0, 0, 0, 0, 0, 0)

    @property
    def weakpoint(self) -> DamageMetrics | None:
        return _damage_metrics(self, "weakpoint_")

    @property
    def resistant(self) -> DamageMetrics | None:
        return _damage_metrics(self, "resistant_")


@dataclass(frozen=True, slots=True)
class DamageResult:
    normal: DamageMetrics
    weakpoint: DamageMetrics | None
    resistant: DamageMetrics | None


@dataclass(frozen=True, slots=True)
class AverageResult:
    normal: DamageMetrics
    weakpoint: DamageMetrics | None
    resistant: DamageMetrics | None
    crit_chance: float
    crit_multiplier: float
    weakpoint_crit_chance: float
    weakpoint_crit_multiplier: float
    sustained_fire_rate: float
    expected_procs_per_attack: float
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
class AverageAttackStats(DamagePool):
    crit_chance: float = 0
    crit_multiplier: float = 1
    weakpoint_crit_chance: float = 0
    weakpoint_crit_multiplier: float = 1
    sustained_fire_rate: float = 0
    procs_per_shot: float = 0
    flat_dph: float | None = None
    flat_dps: float | None = None
    flat_dotph: float | None = None
    flat_dotps: float | None = None
    total_dph: float | None = None
    total_dps: float | None = None
    flat_weakpoint_dph: float | None = None
    flat_weakpoint_dps: float | None = None
    flat_weakpoint_dotph: float | None = None
    flat_weakpoint_dotps: float | None = None
    total_weakpoint_dph: float | None = None
    total_weakpoint_dps: float | None = None
    flat_resistant_dph: float | None = None
    flat_resistant_dps: float | None = None
    flat_resistant_dotph: float | None = None
    flat_resistant_dotps: float | None = None
    total_resistant_dph: float | None = None
    total_resistant_dps: float | None = None
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
class SpatialMetrics(DamagePool):
    falloff_multiplier: float | None = None
    damage_mass: float | None = None
    dimension: int | None = None
    flat_dph: float | None = None
    flat_dotph: float | None = None
    total_dph: float | None = None
    flat_dps: float | None = None
    flat_dotps: float | None = None
    total_dps: float | None = None
    flat_weakpoint_dph: float | None = None
    flat_weakpoint_dotph: float | None = None
    total_weakpoint_dph: float | None = None
    flat_weakpoint_dps: float | None = None
    flat_weakpoint_dotps: float | None = None
    total_weakpoint_dps: float | None = None
    flat_resistant_dph: float | None = None
    flat_resistant_dotph: float | None = None
    total_resistant_dph: float | None = None
    flat_resistant_dps: float | None = None
    flat_resistant_dotps: float | None = None
    total_resistant_dps: float | None = None


@dataclass(slots=True)
class FinalAttackStats(AverageAttackStats):
    pass


@dataclass(slots=True)
class AttackResult:
    name: str
    attack: Attack
    base: BaseAttackStats
    modded: ModdedAttackStats
    effective: EffectiveAttackStats
    upgrades: ResolvedStats
    evolutions: ResolvedStats
    average: AverageResult
    final: FinalAttackStats
    spatial: SpatialMetrics
    status_effects: dict[str, float] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    original_damage: Dist = field(default_factory=Dist)


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
    normal: SpatialDamageMetrics
    weakpoint: SpatialDamageMetrics | None
    resistant: SpatialDamageMetrics | None


@dataclass(frozen=True, slots=True)
class CalculatedAttack:
    name: str
    attack: Attack
    base: BaseAttackStats
    modded: ModdedAttackStats
    effective: EffectiveAttackStats
    upgrades: ResolvedStats
    evolutions: ResolvedStats
    average: AverageResult
    final: DamageResult
    status: StatusResult
    spatial: SpatialResult | None
    children: tuple[str, ...]
    original_damage: Dist


@dataclass(frozen=True, slots=True)
class AggregateResult:
    name: str
    final: DamageResult
    status: StatusResult
    spatial: dict[str, SpatialResult]
    components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalculationResult:
    aggregate: AggregateResult
    attacks: dict[str, CalculatedAttack]
    selected_attack: str
    weapon: Weapon
    target: Enemy | None
    loadout: Loadout
    state: dict[str, object]
