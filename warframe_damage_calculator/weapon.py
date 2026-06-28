from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self

from .dist import Dist
from .upgrade import Upgrade

@dataclass
class Weapon:
    base_damage_dist: Dist = field(default_factory=Dist)
    forced_procs: Dist = field(default_factory=Dist)
    base_crit_chance: float = 0.0
    base_crit_damage: float = 0.0
    base_status_chance: float = 0.0
    
    def __post_init__(self) -> None:
        self.base_total_damage = self.base_damage_dist.total_damage
        self.configure(Upgrade())

    def _compute_moded_stats(self) -> None:
        self.moded_multiplicative_base_damage = 1 + self.config.multiplicative_base_damage
        self.moded_base_damage = 1 + self.config.base_damage
        self.moded_damage_dist = self.moded_base_damage * self.base_damage_dist.apply(self.config.damage_dist).combine()
        self.moded_total_damage = self.moded_damage_dist.total_damage
        self.moded_faction_damage = 1 + self.config.faction_damage
        self.moded_flat_crit_chance = self.config.flat_crit_chance
        self.moded_multiplicative_crit_chance = 1 + self.config.multiplicative_crit_chance
        self.moded_crit_chance = self.base_crit_chance * (1 + self.config.crit_chance)
        self.moded_flat_crit_damage = self.config.flat_crit_damage
        self.moded_crit_damage = self.base_crit_damage * (1 + self.config.crit_damage)
        self.moded_status_chance = self.base_status_chance * (1 + self.config.status_chance)
        self.moded_status_damage = 1 + self.config.status_damage

    def _compute_effective_stats(self) -> None:
        self.effective_base_damage = self.moded_base_damage * self.moded_multiplicative_base_damage
        self.effective_damage_dist = self.moded_multiplicative_base_damage * self.moded_damage_dist
        self.effective_total_damage = self.effective_damage_dist.total_damage
        self.effective_faction_damage = self.moded_faction_damage
        self.effective_crit_chance = self.moded_crit_chance * self.moded_multiplicative_crit_chance + self.moded_flat_crit_chance
        self.effective_crit_damage = self.moded_crit_damage + self.moded_flat_crit_damage
        self.effective_status_chance = self.moded_status_chance
        self.effective_status_damage = self.moded_status_damage

    def configure(self, *upgrades: Upgrade) -> Self:
        self.config = sum(upgrades)
        self._compute_moded_stats()
        self._compute_effective_stats()
        return self

    def crit_probability_for_tier(self, tier: int) -> float:
        return max(0, 1 - abs(self.effective_crit_chance - tier))
    
    def crit_multiplier_for_tier(self, tier: int) -> float:
        return 1 + tier * (self.effective_crit_damage - 1)
    
    def average_crit_multiplier(self) -> float:
        return 1 + self.effective_crit_chance * (self.effective_crit_damage - 1)

    def total_dph(self) -> float:
        return self.flat_dph() + self.flat_dotph()

    def total_dps(self) -> float:
        return self.flat_dps() + self.flat_dotps()
