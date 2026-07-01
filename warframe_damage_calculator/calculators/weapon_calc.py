from __future__ import annotations

class WeaponCalculator:
    def __init__(self, weapon) -> None:
        self.weapon = weapon
    
    def average_crit_multiplier(self) -> float:
        return 1 + self.weapon.effective.crit_chance * (self.weapon.effective.crit_damage - 1)
    
    def crit_probability_for(self, tier: int) -> float:
        return max(0, 1 - abs(self.weapon.effective.crit_chance - tier))
    
    def crit_multiplier_for(self, tier: int) -> float:
        return 1 + tier * (self.weapon.effective.crit_damage - 1)
    
    def total_dph(self) -> float:
        return self.flat_dph() + self.flat_dotph()
    
    def total_dps(self) -> float:
        return self.flat_dps() + self.flat_dotps()
