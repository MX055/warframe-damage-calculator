from __future__ import annotations
from dataclasses import dataclass, field
from .dist import dist
from .upgrade import upgrade

DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))

@dataclass
class weapon:
    base_damage_dist: dist = field(default_factory=dist)
    base_crit_chance: float = 0.0
    base_crit_damage: float = 0.0
    base_status_chance: float = 0.0
    base_total_damage: float = field(init=False)
    config: upgrade = field(init=False)
    moded_multiplicative_base_damage: float = field(init=False)
    moded_base_damage: float = field(init=False)
    moded_damage_dist: dist = field(init=False)
    moded_total_damage: float = field(init=False)
    moded_faction_damage: float = field(init=False)
    moded_flat_crit_chance: float = field(init=False)
    moded_multiplicative_crit_chance: float = field(init=False)
    moded_crit_chance: float = field(init=False)
    moded_flat_crit_damage: float = field(init=False)
    moded_crit_damage: float = field(init=False)
    moded_status_chance: float = field(init=False)
    moded_status_damage: float = field(init=False)
    
    def __post_init__(self) -> None:
        self.base_total_damage = self.base_damage_dist.total_damage
        self.configure(upgrade())
    
    def configure(self, *upgrades: upgrade) -> weapon:
        config = sum(upgrades)
        self.config = config
        self.moded_multiplicative_base_damage = 1 + config.multiplicative_base_damage
        self.moded_base_damage = 1 + config.base_damage
        self.moded_damage_dist = self.moded_base_damage * self.moded_multiplicative_base_damage * self.base_damage_dist.apply(config.damage_dist).combine()
        self.moded_total_damage = self.moded_damage_dist.total_damage
        self.moded_faction_damage = 1 + config.faction_damage
        self.moded_flat_crit_chance = config.flat_crit_chance
        self.moded_multiplicative_crit_chance = 1 + config.multiplicative_crit_chance
        self.moded_crit_chance = self.base_crit_chance * (1 + config.crit_chance)
        self.moded_flat_crit_damage = config.flat_crit_damage
        self.moded_crit_damage = self.base_crit_damage * (1 + config.crit_damage)
        self.moded_status_chance = self.base_status_chance * (1 + config.status_chance)
        self.moded_status_damage = 1 + config.status_damage
        return self

    def effective_crit_chance(self) -> float:
        return self.moded_crit_chance * self.moded_multiplicative_crit_chance + self.moded_flat_crit_chance
    
    def effective_crit_damage(self) -> float:
        return self.moded_crit_damage + self.moded_flat_crit_damage

    def crit_probability_for_tier(self, tier: int) -> float:
        return max(0, 1 - abs(self.effective_crit_chance() - tier))
    
    def crit_multiplier_for_tier(self, tier: int) -> float:
        return 1 + tier * (self.effective_crit_damage() - 1)
