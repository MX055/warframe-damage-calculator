"""Build contribution analysis (removal and Shapley), separate from the attack pipeline."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from math import factorial

from ..core.data import Data
from ..fields.evolution_data import ResolvedEvolutionStat
from ..fields.upgrade_data import ResolvedStat
from ..protocols import BuildUpgradeOwner
from .stat_aggregation import merge_resolved_stat


class ContributionCalculator:
    """Repeatedly evaluates coalition builds against a metric oracle."""

    def __init__(self, *, upgrades: Sequence[BuildUpgradeOwner], weapon_data: Data, resolved_evolutions: ResolvedEvolutionStat, metric_for_build: Callable[[ResolvedStat, ResolvedEvolutionStat, Sequence[BuildUpgradeOwner]], float], upgrade_depends_on_equipped: Callable[[BuildUpgradeOwner], bool]) -> None:
        self._upgrades = list(upgrades)
        self._weapon_data = weapon_data
        self._resolved_evolutions = resolved_evolutions
        self._metric_for_build = metric_for_build
        self._names = [str(upgrade.data.name or "") for upgrade in self._upgrades]
        self._count = len(self._upgrades)
        self._depends_on_equipped = [upgrade_depends_on_equipped(upgrade) for upgrade in self._upgrades]
        self._cached_totals: list[ResolvedStat | None] = [None] * self._count
        self._modular_totals: dict[tuple[int, int], ResolvedStat] = {}

        for index, upgrade in enumerate(self._upgrades):
            if self._depends_on_equipped[index]: continue
            upgrade.results.resolve(weapon_data, Data({"equipped": self._names}))
            self._cached_totals[index] = upgrade.results.total

    def _total_for(self, index: int, mask: int) -> ResolvedStat:
        cached = self._cached_totals[index]
        if cached is not None: return cached
        key = (index, mask)
        cached = self._modular_totals.get(key)
        if cached is None:
            equipped = [self._names[other] for other in range(self._count) if mask & (1 << other)]
            self._upgrades[index].results.resolve(self._weapon_data, Data({"equipped": equipped}))
            cached = self._upgrades[index].results.total
            self._modular_totals[key] = cached
        return cached

    def _metric_for_coalition(self, mask: int) -> float:
        resolved_build = ResolvedStat()
        for index in range(self._count):
            if mask & (1 << index): merge_resolved_stat(resolved_build, self._total_for(index, mask))
        upgrades = [upgrade for index, upgrade in enumerate(self._upgrades) if mask & (1 << index)]
        return self._metric_for_build(resolved_build, self._resolved_evolutions, upgrades)

    def removal_contributions(self) -> dict[str, float]:
        if not self._count: return {}
        full_mask = (1 << self._count) - 1
        full_metric = self._metric_for_coalition(full_mask)
        return {self._names[index]: full_metric - self._metric_for_coalition(full_mask ^ (1 << index)) for index in range(self._count)}

    def shapley_contributions(self) -> dict[str, float]:
        if not self._count: return {}
        count = self._count
        coalition_metrics = [self._metric_for_coalition(mask) for mask in range(1 << count)]
        contributions = [0.0] * count
        denominator = factorial(count)
        for mask in range(1 << count):
            size = mask.bit_count()
            if size == count: continue
            weight = factorial(size) * factorial(count - size - 1) / denominator
            baseline = coalition_metrics[mask]
            for index in range(count):
                bit = 1 << index
                if mask & bit: continue
                contributions[index] += weight * (coalition_metrics[mask | bit] - baseline)

        total = sum(contributions) or 1
        return {self._names[index]: contributions[index] / total for index in range(count)}
