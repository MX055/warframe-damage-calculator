from typing import Any

from ..models.fields import AverageStats, CalculatedStats
from ..models.upgrade import Upgrade


class WeaponCalculator:
    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon
        self.base = CalculatedStats(self.weapon.data.stats.with_defaults())
        self.modded = CalculatedStats()
        self.effective = CalculatedStats()
        self.average = AverageStats()
        self.recompute()
    
    def _compute_modded_stats(self) -> None:
        self.modded.multiplicative_base_damage = max(1 + self.weapon.build.stats.total.multiplicative_base_damage, 1)
        self.modded.base_damage = max(1 + self.weapon.build.stats.total.base_damage, 0)
        self.modded.damage = self.modded.base_damage * self.base.damage.apply(self.weapon.build.stats.total.damage).combine().sorted()
        self.modded.faction_damage = max(1 + self.weapon.build.stats.total.faction_damage, 1)
        self.modded.flat_crit_chance = max(self.weapon.build.stats.total.flat_crit_chance, 0)
        self.modded.multiplicative_crit_chance = max(1 + self.weapon.build.stats.total.multiplicative_crit_chance, 1)
        self.modded.crit_chance = max(self.base.crit_chance * (1 + self.weapon.build.stats.total.crit_chance), 0)
        self.modded.flat_crit_damage = max(self.weapon.build.stats.total.flat_crit_damage, 0)
        self.modded.crit_damage = max(self.base.crit_damage * (1 + self.weapon.build.stats.total.crit_damage), 1)
        self.modded.status_chance = max(self.base.status_chance * (1 + self.weapon.build.stats.total.status_chance), 0)
        self.modded.status_damage = max(1 + self.weapon.build.stats.total.status_damage, 1)

    def _compute_effective_stats(self) -> None:
        self.effective.base_damage = self.modded.base_damage * self.modded.multiplicative_base_damage
        self.effective.damage = self.modded.multiplicative_base_damage * self.modded.damage
        self.effective.faction_damage = self.modded.faction_damage
        self.effective.crit_chance = self.modded.crit_chance * self.modded.multiplicative_crit_chance + self.modded.flat_crit_chance
        self.effective.crit_damage = self.modded.crit_damage + self.modded.flat_crit_damage
        self.effective.status_chance = self.modded.status_chance
        self.effective.status_damage = self.modded.status_damage

    def _compute_average_stats(self) -> None:
        self.average.crit_chance = self.effective.crit_chance
        self.average.crit_multiplier = 1 + self.average.crit_chance * (self.effective.crit_damage - 1)

    def recompute(self) -> None:
        self.weapon.build.stats.resolve(self.weapon.data)
        self._compute_modded_stats()
        self._compute_effective_stats()
        self._compute_average_stats()

    def contribution(self, upgrade: Upgrade) -> float:
        full = self.weapon.build
        if all(equipped.data != upgrade.data for equipped in full):
            return 0.0
        reduced = full - upgrade
        full_dps = self.average.total_dps
        try:
            self.weapon.build = reduced
            self.recompute()
            return full_dps - self.average.total_dps
        finally:
            self.weapon.build = full
            self.recompute()

    def contribution_values(self) -> dict[str, float]:
        return {str(upgrade.data.context.name): self.contribution(upgrade) for upgrade in self.weapon.build}

    def contribution_proportions(self) -> dict[str, float]:
        contributions = self.contribution_values()
        total = sum(contributions.values()) or 1
        return {name: contribution / total for name, contribution in contributions.items()}
