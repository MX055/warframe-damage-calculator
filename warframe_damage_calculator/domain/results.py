from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .damage import Dist
from .upgrades import ResolvedEffect


class Stats(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try: return self[name]
        except KeyError: raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StatusModelProtocol(Protocol):
    expected_procs_per_attack: float


class AttackDefinitionProtocol(Protocol):
    name: str
    children: list[str]


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
    status_model: StatusModelProtocol
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


@dataclass(slots=True)
class AverageAttackStats:
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
class DensityMetrics:
    falloff_multiplier: float | None = None
    damage_mass: float | None = None
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
    attack: AttackDefinitionProtocol
    base: BaseAttackStats
    modded: ModdedAttackStats
    effective: EffectiveAttackStats
    build: ResolvedStats
    evolutions: ResolvedStats
    average: AverageAttackStats
    final: FinalAttackStats
    density: DensityMetrics
    status_effects: dict[str, float] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    original_damage: Dist = field(default_factory=Dist)
