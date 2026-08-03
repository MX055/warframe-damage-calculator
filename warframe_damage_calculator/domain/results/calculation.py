from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ..damage import Dist
from ..enemies import Enemy
from ..builds import Build
from ..state import State
from ..status import StatusModel
from ..upgrades import ResolvedEffect
from ..weapons import Weapon
from .damage import AttackCriticalMetrics, AttackDamageMetrics, AttackTimingMetrics, DamageResult
from .spatial import AttackSpatialMetrics
from .status import AttackStatusMetrics


class AttackStatsResult(Protocol):
    damage: Dist
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float
    def get(self, name: str, default: float | Dist | None = None) -> float | int | bool | str | Dist | StatusModel | tuple[ResolvedEffect, ...] | dict[str, float] | None: ...


class ResolvedStatsResult(Protocol):
    proportional: Mapping[str, float | Dist]
    multiplicative: Mapping[str, float | Dist]
    base: Mapping[str, float | Dist]
    flat: Mapping[str, float | Dist]
    families: Mapping[str, Mapping[str, float | Dist]]
    maximums: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class AttackResult:
    base: AttackStatsResult
    modded: AttackStatsResult
    effective: AttackStatsResult
    upgrades: ResolvedStatsResult
    evolutions: ResolvedStatsResult
    damage: AttackDamageMetrics
    critical: AttackCriticalMetrics
    timing: AttackTimingMetrics
    status: AttackStatusMetrics
    spatial: AttackSpatialMetrics
    generated_by: str | None = None
    generated_from: str | None = None


@dataclass(frozen=True, slots=True)
class AggregateResult:
    damage: DamageResult
    status: AttackStatusMetrics


@dataclass(frozen=True, slots=True)
class CalculationResult:
    aggregate: AggregateResult
    attacks: dict[str, AttackResult]
    selected_attack: str
    selected_body_part: str
    weapon: Weapon
    target: Enemy | None
    build: Build
    state: State
