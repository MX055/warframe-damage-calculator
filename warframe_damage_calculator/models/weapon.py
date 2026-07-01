from __future__ import annotations

from typing import Self

from ..mechanics import WeaponState
from .upgrade import Upgrade


class Weapon[TWeaponState: WeaponState]:
    def __init__(self, base: TWeaponState) -> None:
        self.base = base
        self.base.total_damage = self.base.damage_dist.total_damage
        self.moded: TWeaponState = type(self.base)()
        self.effective: TWeaponState = type(self.base)()
        self.configure(Upgrade())

    def _compute_moded_stats(self) -> None:
        self.moded.multiplicative_base_damage = max(1 + self.config.multiplicative_base_damage, 1)
        self.moded.base_damage = max(1 + self.config.base_damage, 0)
        self.moded.damage_dist = self.moded.base_damage * self.base.damage_dist.apply(self.config.damage_dist).combine()
        self.moded.total_damage = self.moded.damage_dist.total_damage
        self.moded.faction_damage = max(1 + self.config.faction_damage, 1)
        self.moded.flat_crit_chance = max(self.config.flat_crit_chance, 0)
        self.moded.multiplicative_crit_chance = max(1 + self.config.multiplicative_crit_chance, 1)
        self.moded.crit_chance = max(self.base.crit_chance * (1 + self.config.crit_chance), 0)
        self.moded.flat_crit_damage = max(self.config.flat_crit_damage, 0)
        self.moded.crit_damage = max(self.base.crit_damage * (1 + self.config.crit_damage), 1)
        self.moded.status_chance = max(self.base.status_chance * (1 + self.config.status_chance), 0)
        self.moded.status_damage = max(1 + self.config.status_damage, 1)

    def _compute_effective_stats(self) -> None:
        self.effective.base_damage = self.moded.base_damage * self.moded.multiplicative_base_damage
        self.effective.damage_dist = self.moded.multiplicative_base_damage * self.moded.damage_dist
        self.effective.total_damage = self.effective.damage_dist.total_damage
        self.effective.faction_damage = self.moded.faction_damage
        self.effective.crit_chance = self.moded.crit_chance * self.moded.multiplicative_crit_chance + self.moded.flat_crit_chance
        self.effective.crit_damage = self.moded.crit_damage + self.moded.flat_crit_damage
        self.effective.status_chance = self.moded.status_chance
        self.effective.status_damage = self.moded.status_damage

    def configure(self, *upgrades: Upgrade) -> Self:
        self.config = sum(upgrades)
        self._compute_moded_stats()
        self._compute_effective_stats()
        return self

    def crit_probability_for_tier(self, tier: int) -> float:
        return max(0, 1 - abs(self.effective.crit_chance - tier))
    
    def crit_multiplier_for_tier(self, tier: int) -> float:
        return 1 + tier * (self.effective.crit_damage - 1)
    
    def average_crit_multiplier(self) -> float:
        return 1 + self.effective.crit_chance * (self.effective.crit_damage - 1)

    def total_dph(self) -> float:
        return self.flat_dph() + self.flat_dotph()

    def total_dps(self) -> float:
        return self.flat_dps() + self.flat_dotps()
