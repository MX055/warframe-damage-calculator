from __future__ import annotations

from ..utils import DOT_MULTIPLIERS, true_round
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator):

    def melee_doughty_bonus(self) -> float:
        return true_round(10 * self.weapon.effective.damage_dist.weight("puncture") * self.weapon.effective.status_chance * self.weapon.effective.melee_doughty, 1)
    
    def average_melee_duplicate_multiplier(self) -> float:
        return 1 + self.weapon.effective.melee_duplicate * max(0, 1 - abs(self.weapon.effective.crit_chance - 1))
    
    def flat_dph(self) -> float:
        return self.weapon.effective.total_damage * self.weapon.effective.faction_damage * self.average_crit_multiplier() * self.average_melee_duplicate_multiplier()
    
    def flat_dps(self) -> float:
        return self.weapon.effective.attack_speed * self.flat_dph()
    
    def flat_dotph(self) -> float:
        return sum(mult * self.weapon.effective.damage_dist.get(dt) * self.weapon.effective.damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.weapon.effective.status_chance * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2 * self.average_crit_multiplier() * self.average_melee_duplicate_multiplier()
    
    def flat_dotps(self) -> float:
        return self.weapon.effective.attack_speed * self.flat_dotph()
