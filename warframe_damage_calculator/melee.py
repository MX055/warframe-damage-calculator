from __future__ import annotations

from dataclasses import dataclass, field

from .constants import DOT_MULTIPLIERS
from .dist import Dist
from .upgrade import Upgrade
from .weapon import Weapon

@dataclass
class Melee(Weapon):
    base_attack_speed: float = 0.0

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded_attack_speed = self.base_attack_speed * (1 + self.config.attack_speed)
        self.moded_melee_duplicate = 1 + self.config.melee_duplicate

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective_attack_speed = self.moded_attack_speed
        self.effective_melee_duplicate = self.moded_melee_duplicate
    
    def average_duplicate_multiplier(self) -> float:
        return 1 + self.effective_melee_duplicate * self.crit_probability_for_tier(1) * (self.crit_probability_for_tier(1) * self.crit_multiplier_for_tier(1) + self.crit_probability_for_tier(2) * self.crit_multiplier_for_tier(2)) / self.average_crit_multiplier()
    
    def flat_dph(self) -> float:
        return self.effective_total_damage * self.effective_faction_damage * self.average_crit_multiplier() * self.average_duplicate_multiplier()
    
    def flat_dps(self) -> float:
        return self.effective_attack_speed * self.flat_dph()
    
    def flat_dotph(self) -> float:
        return sum(mult * self.effective_damage_dist.get(dt) * self.effective_damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective_status_chance * self.effective_status_damage * self.effective_faction_damage**2 * self.average_crit_multiplier() * self.average_duplicate_multiplier()

    def flat_dotps(self) -> float:
        return self.effective_attack_speed * self.flat_dotph()
    
    def summary(self) -> str:
        return "\n".join([
            f"{'ATTACK SPEED:':<14} {f'{self.base_attack_speed:.2f}x':<6} -> {self.effective_attack_speed:.2f}x",
            f"{'CRIT CHANCE:':<14} {f'{self.base_crit_chance:.2%}':<6} -> {self.effective_crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<14} {f'{self.base_crit_damage:.2f}x':<6} -> {self.effective_crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<14} {f'{self.base_status_chance:.2%}':<6} -> {self.effective_status_chance:.2%}",
            f"{'STATUS DAMAGE:':<14} {'1.00x':<6} -> {self.effective_status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<14} {f'{self.base_damage_dist.get(dt):.2f}':<6} -> {self.effective_damage_dist.get(dt):.2f}" for dt, _ in self.effective_damage_dist),
            f"{'TOTAL DAMAGE:':<14} {f'{self.base_total_damage:.2f}':<6} -> {self.effective_total_damage:.2f}",
            "-------------------------------------",
            f"{'FLAT DPH:':<14} {self.flat_dph():.2f}",
            f"{'FLAT DOTPH:':<14} {self.flat_dotph():.2f}",
            f"{'TOTAL DPH:':<14} {self.total_dph():.2f}",
            f"{'FLAT DPS:':<14} {self.flat_dps():.2f} x BASE HPS",
            f"{'FLAT DOTPS:':<14} {self.flat_dotps():.2f} x BASE HPS",
            f"{'TOTAL DPS:':<14} {self.total_dps():.2f} x BASE HPS",
            "-------------------------------------"
        ])