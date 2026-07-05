from __future__ import annotations

from functools import cached_property

from ..states import WeaponState
from ..models import Build


class WeaponCalculator[TWeaponState: WeaponState]:
    """Base calculator for weapon stats.

    Takes a weapon's base stats and a ``Build`` and prepares the
    common stats used by every weapon type.

    Keeps three versions of the stats: ``base`` for the original weapon,
    ``moded`` for stats after normal build bonuses, and ``effective`` for the
    final values used by damage calculations.

    Specialized calculators add hit damage, damage over time, and
    weapon-family mechanics.
    """
    def __init__(self, base: TWeaponState) -> None:
        self.build = Build()
        self.base: TWeaponState = base
        self.moded: TWeaponState = type(base)()
        self.effective: TWeaponState = type(base)()
        self.recompute()

    def _compute_moded_stats(self) -> None:
        self.moded.multiplicative_base_damage = max(1 + self.build.multiplicative_base_damage, 1)
        self.moded.base_damage = max(1 + self.build.base_damage, 0)
        self.moded.damage_dist = self.moded.base_damage * self.base.damage_dist.apply(self.build.damage_dist).combine().sorted()
        self.moded.total_damage = self.moded.damage_dist.total_damage()
        self.moded.faction_damage = max(1 + self.build.faction_damage, 1)
        self.moded.flat_crit_chance = max(self.build.flat_crit_chance, 0)
        self.moded.multiplicative_crit_chance = max(1 + self.build.multiplicative_crit_chance, 1)
        self.moded.crit_chance = max(self.base.crit_chance * (1 + self.build.crit_chance), 0)
        self.moded.flat_crit_damage = max(self.build.flat_crit_damage, 0)
        self.moded.crit_damage = max(self.base.crit_damage * (1 + self.build.crit_damage), 1)
        self.moded.status_chance = max(self.base.status_chance * (1 + self.build.status_chance), 0)
        self.moded.status_damage = max(1 + self.build.status_damage, 1)

    def _compute_effective_stats(self) -> None:
        self.effective.base_damage = self.moded.base_damage * self.moded.multiplicative_base_damage
        self.effective.damage_dist = self.moded.multiplicative_base_damage * self.moded.damage_dist
        self.effective.total_damage = self.effective.damage_dist.total_damage()
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
