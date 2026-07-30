from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import factorial
from typing import Any

from .damage import Dist


class Stats(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try: return self[name]
        except KeyError: raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


@dataclass(slots=True)
class ResolvedStats:
    proportional: Stats = field(default_factory=Stats)
    base: Stats = field(default_factory=Stats)
    flat: Stats = field(default_factory=Stats)
    families: dict[str, Stats] = field(default_factory=dict)
    maximums: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class Metrics:
    crit_chance: float = 0
    crit_multiplier: float = 1
    weakpoint_crit_chance: float = 0
    weakpoint_crit_multiplier: float = 1
    fire_rate: float = 0
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
    damage_mass: float = 0
    damage_density: float | None = None
    damage_density_per_second: float | None = None
    weakpoint_damage_density: float | None = None
    weakpoint_damage_density_per_second: float | None = None
    resistant_damage_density: float | None = None
    resistant_damage_density_per_second: float | None = None


@dataclass(slots=True)
class AttackResult:
    name: str
    attack: Any
    base: Stats
    modded: Stats
    effective: Stats
    build: ResolvedStats
    evolutions: ResolvedStats
    average: Metrics
    final: Metrics
    density: DensityMetrics
    status_effects: dict[str, float] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    original_damage: Dist = field(default_factory=Dist)


class WeaponResults:
    __slots__ = ("weapon", "attacks", "main")

    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon
        self.attacks: dict[str, AttackResult] = {}
        self.main: AttackResult
        self.resolve()

    @property
    def child(self) -> list[AttackResult]:
        return [self.attacks[name] for name in self.main.children]

    def resolve(self) -> None:
        from ..engine.calculator import calculate_weapon
        self.attacks = calculate_weapon(self.weapon)
        self.main = self.attacks[self.weapon.runtime.attack]

    def _metric(self, upgrades: list[Any], target: str) -> float:
        from .upgrades import Build
        copied = self.weapon.copy()
        copied.build = Build(*upgrades)
        copied.results.resolve()
        return float(getattr(copied.results.main.final, target) or 0)

    def removal_contributions(self, target: str = "total_dps") -> dict[str, float]:
        upgrades = list(self.weapon.build)
        baseline = float(getattr(self.main.final, target) or 0)
        return {upgrade.name: baseline - self._metric([candidate for candidate in upgrades if candidate is not upgrade], target) for upgrade in upgrades}

    def shapley_contributions(self, target: str = "total_dps") -> dict[str, float]:
        upgrades = list(self.weapon.build)
        size = len(upgrades)
        if not size: return {}
        empty = self._metric([], target)
        values = {upgrade.name: 0.0 for upgrade in upgrades}
        for index, upgrade in enumerate(upgrades):
            others = [candidate for candidate in upgrades if candidate is not upgrade]
            for subset_size in range(size):
                weight = factorial(subset_size) * factorial(size - subset_size - 1) / factorial(size)
                for subset in combinations(others, subset_size):
                    before = self._metric(list(subset), target)
                    after = self._metric([*subset, upgrade], target)
                    values[upgrade.name] += weight * (after - before)
        total = self._metric(upgrades, target) - empty
        difference = total - sum(values.values())
        if values and abs(difference) > 1e-9: values[next(iter(values))] += difference
        denominator = sum(values.values())
        return {name: value / denominator for name, value in values.items()} if denominator else {name: 0.0 for name in values}
