from __future__ import annotations
from dataclasses import dataclass, field
from .dist import dist
from .weapon import weapon
from .upgrade import upgrade

DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))

@dataclass
class melee(weapon):
    base_attack_speed: float = 0.0
    moded_attack_speed: float = field(init=False)
    moded_melee_duplicate: float = field(init=False)

    def configure(self, *upgrades: upgrade) -> melee:
        super().configure(*upgrades)
        config = self.config
        self.moded_attack_speed = self.base_attack_speed * (1 + config.attack_speed)
        self.moded_melee_duplicate = 1 + config.melee_duplicate
        return self

    def average_crit_multiplier(self) -> float:
        return 1 + self.effective_crit_chance() * (self.effective_crit_damage() - 1)
    
    def average_duplicate_multiplier(self) -> float:
        return 1 + self.moded_melee_duplicate * self.crit_probability_for_tier(1) * (self.crit_probability_for_tier(1) * self.crit_multiplier_for_tier(1) + self.crit_probability_for_tier(2) * self.crit_multiplier_for_tier(2)) / self.average_crit_multiplier()
    
    def flat_dph(self) -> float:
        return self.moded_total_damage * self.moded_faction_damage * self.average_crit_multiplier() * self.average_duplicate_multiplier()
    
    def flat_dps(self) -> float:
        return self.moded_attack_speed * self.flat_dph()
    
    def flat_dotph(self) -> float:
        return sum(mult * self.moded_damage_dist.get(dt) * self.moded_damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.moded_status_chance * self.moded_status_damage * self.moded_faction_damage**2 * self.average_crit_multiplier() * self.average_duplicate_multiplier()

    def flat_dotps(self) -> float:
        return self.moded_attack_speed * self.flat_dotph()
    
    def total_dph(self) -> float:
        return self.flat_dph() + self.flat_dotph()
    
    def total_dps(self) -> float:
        return self.flat_dps() + self.flat_dotps()
    
    def summary(self) -> str:
        return "\n".join([
            f"{'ATTACK SPEED:':<14} {f'{self.base_attack_speed:.2f}x':<6} -> {self.moded_attack_speed:.2f}x",
            f"{'CRIT CHANCE:':<14} {f'{self.base_crit_chance:.2%}':<6} -> {self.effective_crit_chance():.2%}",
            f"{'CRIT DAMAGE:':<14} {f'{self.base_crit_damage:.2f}x':<6} -> {self.effective_crit_damage():.2f}x",
            f"{'STATUS CHANCE:':<14} {f'{self.base_status_chance:.2%}':<6} -> {self.moded_status_chance:.2%}",
            f"{'STATUS DAMAGE:':<14} {'1.00x':<6} -> {self.moded_status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<14} {f'{self.base_damage_dist.get(dt):.2f}':<6} -> {self.moded_damage_dist.get(dt):.2f}" for dt, _ in self.moded_damage_dist if self.moded_damage_dist.get(dt) != 0),
            f"{'TOTAL DAMAGE:':<14} {f'{self.base_total_damage:.2f}':<6} -> {self.moded_total_damage:.2f}",
            "-------------------------------------",
            f"{'FLAT DPH:':<14} {self.flat_dph():.2f}",
            f"{'FLAT DOTPH:':<14} {self.flat_dotph():.2f}",
            f"{'TOTAL DPH:':<14} {self.total_dph():.2f}",
            f"{'FLAT DPS:':<14} {self.flat_dps():.2f} x BASE HPS",
            f"{'FLAT DOTPS:':<14} {self.flat_dotps():.2f} x BASE HPS",
            f"{'TOTAL DPS:':<14} {self.total_dps():.2f} x BASE HPS",
            "-------------------------------------"
        ])