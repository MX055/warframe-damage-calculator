from __future__ import annotations

from ..mechanics.constants import DOT_MULTIPLIERS
from ..mechanics.functions import true_round
from ..mechanics.states import MeleeState
from ..mechanics.dist import dist
from .weapon import Weapon


class Melee(Weapon):
    def __init__(self, damage_dist: dist | None = None, forced_procs: dist | None = None, crit_chance: float = 0.0, crit_damage: float = 0.0, status_chance: float = 0.0, attack_speed: float = 0.0) -> None:
        super().__init__(MeleeState(damage_dist=damage_dist or dist(), forced_procs=forced_procs or dist(), crit_chance=crit_chance, crit_damage=crit_damage, status_chance=status_chance, attack_speed=attack_speed))

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.melee_duplicate = self.config.melee_duplicate
        self.moded.melee_doughty = self.config.melee_doughty
        self.moded.attack_speed = self.base.attack_speed * (1 + self.config.attack_speed)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.melee_duplicate = self.moded.melee_duplicate
        self.effective.melee_doughty = self.moded.melee_doughty
        self.effective.attack_speed = self.moded.attack_speed
        self.effective.crit_damage += self.melee_doughty_bonus()

    def melee_doughty_bonus(self) -> float:
        return true_round(10 * self.effective.damage_dist.weight("puncture") * self.effective.status_chance * self.effective.melee_doughty, 1)
    
    def average_melee_duplicate_multiplier(self) -> float:
        return 1 + self.effective.melee_duplicate * max(0, 1 - abs(self.effective.crit_chance - 1))

    def flat_dph(self) -> float:
        return self.effective.total_damage * self.effective.faction_damage * self.average_crit_multiplier() * self.average_melee_duplicate_multiplier()
    
    def flat_dps(self) -> float:
        return self.effective.attack_speed * self.flat_dph()
    
    def flat_dotph(self) -> float:
        return sum(mult * self.effective.damage_dist.get(dt) * self.effective.damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective.status_chance * self.effective.status_damage * self.effective.faction_damage**2 * self.average_crit_multiplier() * self.average_melee_duplicate_multiplier()

    def flat_dotps(self) -> float:
        return self.effective.attack_speed * self.flat_dotph()
    
    def summary(self) -> str:
        return "\n".join([
            f"{'ATTACK SPEED:':<14} {f'{self.base.attack_speed:.2f}x':<6} -> {self.effective.attack_speed:.2f}x",
            f"{'CRIT CHANCE:':<14} {f'{self.base.crit_chance:.2%}':<6} -> {self.effective.crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<14} {f'{self.base.crit_damage:.2f}x':<6} -> {self.effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<14} {f'{self.base.status_chance:.2%}':<6} -> {self.effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<14} {'1.00x':<6} -> {self.effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<14} {f'{self.base.damage_dist.get(dt):.2f}':<6} -> {self.effective.damage_dist.get(dt):.2f}" for dt, _ in self.effective.damage_dist),
            f"{'TOTAL DAMAGE:':<14} {f'{self.base.total_damage:.2f}':<6} -> {self.effective.total_damage:.2f}",
            "-------------------------------------",
            f"{'FLAT DPH:':<14} {self.flat_dph():.2f}",
            f"{'FLAT DOTPH:':<14} {self.flat_dotph():.2f}",
            f"{'TOTAL DPH:':<14} {self.total_dph():.2f}",
            f"{'FLAT DPS:':<14} {self.flat_dps():.2f} x BASE HPS",
            f"{'FLAT DOTPS:':<14} {self.flat_dotps():.2f} x BASE HPS",
            f"{'TOTAL DPS:':<14} {self.total_dps():.2f} x BASE HPS",
            "-------------------------------------"
        ])