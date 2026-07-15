from functools import cached_property
from collections.abc import Mapping
from typing import Any

from ..models import Data, Dist, Build, Upgrade


class WeaponCalculator:
    DEFAULT_STATS = Data({"damage": Dist(), "forced_procs": Dist(), "crit_chance": 0.0, "crit_damage": 1.0, "status_chance": 0.0})
    CALCULATED_STATS = Data({"total_damage": 0.0, "multiplicative_base_damage": 1.0, "base_damage": 0.0, "faction_damage": 1.0, "flat_crit_chance": 0.0, "multiplicative_crit_chance": 1.0, "flat_crit_damage": 0.0, "status_damage": 1.0})

    def __init__(self, stats: Mapping[str, Any] | None = None, context: Mapping[str, Any] | None = None) -> None:
        self.context = Data(context)
        self.build = Build()
        self.base = self._new_stats(stats)
        self.moded = self._new_stats()
        self.effective = self._new_stats()
        self.recompute()

    @classmethod
    def _new_stats(cls, stats: Mapping[str, Any] | None = None) -> Data:
        values = cls.DEFAULT_STATS | cls.CALCULATED_STATS | Data(stats)
        values.total_damage = values.damage.total_damage()
        if "explosion_damage" in values:
            values.explosion_total_damage = values.explosion_damage.total_damage()
        return values

    def _compute_moded_stats(self) -> None:
        self.moded.multiplicative_base_damage = max(1 + self.build.get("multiplicative_base_damage"), 1)
        self.moded.base_damage = max(1 + self.build.get("base_damage"), 0)
        self.moded.damage = self.moded.base_damage * self.base.damage.apply(self.build.get("damage", Dist())).combine().sorted()
        self.moded.total_damage = self.moded.damage.total_damage()
        self.moded.faction_damage = max(1 + self.build.get("faction_damage"), 1)
        self.moded.flat_crit_chance = max(self.build.get("flat_crit_chance"), 0)
        self.moded.multiplicative_crit_chance = max(1 + self.build.get("multiplicative_crit_chance"), 1)
        self.moded.crit_chance = max(self.base.crit_chance * (1 + self.build.get("crit_chance")), 0)
        self.moded.flat_crit_damage = max(self.build.get("flat_crit_damage"), 0)
        self.moded.crit_damage = max(self.base.crit_damage * (1 + self.build.get("crit_damage")), 1)
        self.moded.status_chance = max(self.base.status_chance * (1 + self.build.get("status_chance")), 0)
        self.moded.status_damage = max(1 + self.build.get("status_damage"), 1)

    def _compute_effective_stats(self) -> None:
        self.effective.base_damage = self.moded.base_damage * self.moded.multiplicative_base_damage
        self.effective.damage = self.moded.multiplicative_base_damage * self.moded.damage
        self.effective.total_damage = self.effective.damage.total_damage()
        self.effective.faction_damage = self.moded.faction_damage
        self.effective.crit_chance = self.moded.crit_chance * self.moded.multiplicative_crit_chance + self.moded.flat_crit_chance
        self.effective.crit_damage = self.moded.crit_damage + self.moded.flat_crit_damage
        self.effective.status_chance = self.moded.status_chance
        self.effective.status_damage = self.moded.status_damage

    def _clear_cached_properties(self) -> None:
        for cls in type(self).mro():
            for name, attr in cls.__dict__.items():
                if isinstance(attr, cached_property):
                    self.__dict__.pop(name, None)

    def recompute(self) -> None:
        self._compute_moded_stats()
        self._compute_effective_stats()
        self._clear_cached_properties()

    def set_build(self, build: Build) -> None:
        self.build = build.resolve(self.context)
        self.recompute()

    def contribution(self, upgrade: Upgrade) -> float:
        full = self.build
        full_dps = self.total_dps
        self.build = self.build - upgrade
        self.recompute()
        contribution = full_dps - self.total_dps
        self.build = full
        self.recompute()
        return contribution

    @cached_property
    def average_crit_chance(self) -> float:
        return self.effective.crit_chance

    @cached_property
    def average_crit_multiplier(self) -> float:
        return 1 + self.average_crit_chance * (self.effective.crit_damage - 1)

    @cached_property
    def total_dph(self) -> float:
        return self.flat_dph + self.flat_dotph

    @cached_property
    def total_dps(self) -> float:
        return self.flat_dps + self.flat_dotps

    def contribution_values(self) -> dict[str, float]:
        return {str(upgrade.context.name): self.contribution(upgrade) for upgrade in self.build}

    def contribution_proportions(self) -> dict[str, float]:
        contributions = self.contribution_values()
        total = sum(contributions.values()) or 1
        return {name: contribution / total for name, contribution in contributions.items()}
