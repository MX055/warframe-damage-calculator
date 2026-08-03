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
from .damage import AverageResult, DamageResult
from .spatial import SpatialResult
from .status import StatusResult


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
class CalculatedAttack:
    base: AttackStatsResult
    modded: AttackStatsResult
    effective: AttackStatsResult
    upgrades: ResolvedStatsResult
    evolutions: ResolvedStatsResult
    average: AverageResult
    status: StatusResult
    spatial: SpatialResult | None
    generated_by: str | None = None
    generated_from: str | None = None


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
    build: Build
    state: State
