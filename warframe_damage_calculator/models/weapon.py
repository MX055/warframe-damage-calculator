from __future__ import annotations

from typing import Self

from .states import WeaponState
from .upgrade import Upgrade
from .build import Build


class Weapon[TWeaponState: WeaponState]:
    _calculator_class = None
    _formatter_class = None

    def __init__(self, base: TWeaponState) -> None:
        self.base = base
        self.base.total_damage = self.base.damage_dist.total_damage
        self.moded: TWeaponState = type(self.base)()
        self.effective: TWeaponState = type(self.base)()
        self.configure(Upgrade())

    def _compute_moded_stats(self) -> None:
        self.moded.multiplicative_base_damage = max(1 + self.build.multiplicative_base_damage, 1)
        self.moded.base_damage = max(1 + self.build.base_damage, 0)
        self.moded.damage_dist = self.moded.base_damage * self.base.damage_dist.apply(self.build.damage_dist).combine()
        self.moded.total_damage = self.moded.damage_dist.total_damage
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
        self.effective.total_damage = self.effective.damage_dist.total_damage
        self.effective.faction_damage = self.moded.faction_damage
        self.effective.crit_chance = self.moded.crit_chance * self.moded.multiplicative_crit_chance + self.moded.flat_crit_chance
        self.effective.crit_damage = self.moded.crit_damage + self.moded.flat_crit_damage
        self.effective.status_chance = self.moded.status_chance
        self.effective.status_damage = self.moded.status_damage

    def configure(self, *args: Build | Upgrade) -> Self:
        if isinstance(args[0], Build) and len(args) == 1:
            self.build = args[0]
        elif all(isinstance(arg, Upgrade) for arg in args):
            self.build = Build(*args)
        else:
            raise TypeError
        
        self._compute_moded_stats()
        self._compute_effective_stats()
        return self
    
    @property
    def calculate(self):
        if self._calculator_class is None:
            raise NotImplementedError
        return self._calculator_class(self)

    @property
    def format(self):
        if self._formatter_class is None:
            raise NotImplementedError
        return self._formatter_class(self, self.calculate)