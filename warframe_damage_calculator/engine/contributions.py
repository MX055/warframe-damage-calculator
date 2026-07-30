from __future__ import annotations

from math import factorial
from typing import Protocol

from ..domain.results import AttackResult
from ..domain.upgrades import Build, Upgrade


class ResultsProtocol(Protocol):
    main: AttackResult

    def resolve(self) -> None: ...


class ContributionWeaponProtocol(Protocol):
    build: Build
    results: ResultsProtocol

    def copy(self, *, resolve: bool = True) -> ContributionWeaponProtocol: ...


def _metric(weapon: ContributionWeaponProtocol, upgrades: list[Upgrade], target: str) -> float:
    copied = weapon.copy(resolve=False)
    copied.build = Build(*upgrades)
    copied.results.resolve()
    return float(getattr(copied.results.main.final, target) or 0)


def removal_contributions(weapon: ContributionWeaponProtocol, target: str) -> dict[str, float]:
    upgrades = list(weapon.build)
    baseline = float(getattr(weapon.results.main.final, target) or 0)
    return {upgrade.name: baseline - _metric(weapon, [candidate for candidate in upgrades if candidate is not upgrade], target) for upgrade in upgrades}


def shapley_contributions(weapon: ContributionWeaponProtocol, target: str) -> dict[str, float]:
    upgrades = list(weapon.build)
    size = len(upgrades)
    if not size: return {}
    coalition_values: dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in coalition_values: coalition_values[mask] = _metric(weapon, [upgrade for index, upgrade in enumerate(upgrades) if mask & (1 << index)], target)
        return coalition_values[mask]

    empty = coalition_value(0)
    values = {upgrade.name: 0.0 for upgrade in upgrades}
    for index, upgrade in enumerate(upgrades):
        upgrade_bit = 1 << index
        for mask in range(1 << size):
            if mask & upgrade_bit: continue
            subset_size = mask.bit_count()
            weight = factorial(subset_size) * factorial(size - subset_size - 1) / factorial(size)
            values[upgrade.name] += weight * (coalition_value(mask | upgrade_bit) - coalition_value(mask))
    total = coalition_value((1 << size) - 1) - empty
    difference = total - sum(values.values())
    if values and abs(difference) > 1e-9: values[next(iter(values))] += difference
    denominator = sum(values.values())
    return {name: value / denominator for name, value in values.items()} if denominator else {name: 0.0 for name in values}
