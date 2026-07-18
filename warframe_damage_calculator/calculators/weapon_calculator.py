from collections.abc import Mapping
from typing import Any

from ..models.data import Data
from ..models.dist import Dist
from ..models.upgrade import Upgrade


class WeaponCalculator:
    DIST_FIELDS = {"damage", "forced_procs"}
    DEFAULT_STATS = Data({"damage": Dist(), "forced_procs": Dist(), "crit_chance": 0.0, "crit_damage": 1.0, "status_chance": 0.0, "total_damage": 0.0, "multiplicative_base_damage": 1.0, "base_damage": 0.0, "faction_damage": 1.0, "flat_crit_chance": 0.0, "multiplicative_crit_chance": 1.0, "flat_crit_damage": 0.0, "status_damage": 1.0})
    DEFAULT_BUILD = Data({"damage": Dist(), "multiplicative_base_damage": 0.0, "base_damage": 0.0, "faction_damage": 0.0, "flat_crit_chance": 0.0, "multiplicative_crit_chance": 0.0, "crit_chance": 0.0, "flat_crit_damage": 0.0, "crit_damage": 0.0, "status_chance": 0.0, "status_damage": 0.0})

    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon
        self.base = self._base(self.weapon.data.stats)
        self.moded = Data()
        self.effective = Data()
        self.average = Data()
        self.recompute()

    @classmethod
    def _base(cls, stats: Data | None = None) -> Data:
        values = cls.DEFAULT_STATS | stats
        for field in cls.DIST_FIELDS:
            values[field] = Dist(values.get(field))
        values.total_damage = values.damage.total_damage()
        return values
    
    def _compute_moded_stats(self) -> None:
        self.moded.multiplicative_base_damage = max(1 + self.weapon.build.stats.total.multiplicative_base_damage, 1)
        self.moded.base_damage = max(1 + self.weapon.build.stats.total.base_damage, 0)
        self.moded.damage = self.moded.base_damage * self.base.damage.apply(self.weapon.build.stats.total.damage).combine().sorted()
        self.moded.total_damage = self.moded.damage.total_damage()
        self.moded.faction_damage = max(1 + self.weapon.build.stats.total.faction_damage, 1)
        self.moded.flat_crit_chance = max(self.weapon.build.stats.total.flat_crit_chance, 0)
        self.moded.multiplicative_crit_chance = max(1 + self.weapon.build.stats.total.multiplicative_crit_chance, 1)
        self.moded.crit_chance = max(self.base.crit_chance * (1 + self.weapon.build.stats.total.crit_chance), 0)
        self.moded.flat_crit_damage = max(self.weapon.build.stats.total.flat_crit_damage, 0)
        self.moded.crit_damage = max(self.base.crit_damage * (1 + self.weapon.build.stats.total.crit_damage), 1)
        self.moded.status_chance = max(self.base.status_chance * (1 + self.weapon.build.stats.total.status_chance), 0)
        self.moded.status_damage = max(1 + self.weapon.build.stats.total.status_damage, 1)

    def _compute_effective_stats(self) -> None:
        self.effective.base_damage = self.moded.base_damage * self.moded.multiplicative_base_damage
        self.effective.damage = self.moded.multiplicative_base_damage * self.moded.damage
        self.effective.total_damage = self.effective.damage.total_damage()
        self.effective.faction_damage = self.moded.faction_damage
        self.effective.crit_chance = self.moded.crit_chance * self.moded.multiplicative_crit_chance + self.moded.flat_crit_chance
        self.effective.crit_damage = self.moded.crit_damage + self.moded.flat_crit_damage
        self.effective.status_chance = self.moded.status_chance
        self.effective.status_damage = self.moded.status_damage

    def _compute_average_stats(self) -> None:
        self.average.crit_chance = self.effective.crit_chance
        self.average.crit_multiplier = 1 + self.average.crit_chance * (self.effective.crit_damage - 1)

    def recompute(self) -> None:
        self.weapon.build.stats.resolve(self.weapon.data)
        self.weapon.build.stats.total = self.DEFAULT_BUILD.copy() | self.weapon.build.stats.total
        self._compute_moded_stats()
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
