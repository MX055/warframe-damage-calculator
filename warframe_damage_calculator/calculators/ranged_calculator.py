from __future__ import annotations

from .weapon_calculator import WeaponCalculator


class RangedCalculator(WeaponCalculator):

    def average_fire_rate(self) -> float:
        if self.weapon.effective.magazine_capacity == 1:
            return 1 / self.weapon.effective.reload_speed
        return (self.weapon.effective.magazine_capacity / (1 - self.weapon.effective.ammo_efficiency)) / (self.weapon.effective.magazine_capacity / (1 - self.weapon.effective.ammo_efficiency) * (1 / self.weapon.effective.fire_rate + self.weapon.effective.charge_time) + self.weapon.effective.reload_speed)

    def average_procs_per_shot(self) -> float:
        return self.weapon.effective.status_chance * self.weapon.effective.multishot
    
    def average_weakpoint_crit_multiplier(self) -> float:
        return 1 + self.weapon.effective.weakpoint_crit_chance * (self.weapon.effective.crit_damage - 1)
    
    def weakpoint_crit_probability_for(self, tier: int) -> float:
        return max(0, 1 - abs(self.weapon.effective.weakpoint_crit_chance - tier))
    
    def beam_dot_multiplier(self) -> float:
        return self.weapon.effective.multishot if self.weapon.base.is_beam else 1
    
    def flat_dph(self) -> float:
        return (self.weapon.effective.total_damage * self.weapon.effective.multishot + self.weapon.effective.explosion_total_damage) * self.weapon.effective.faction_damage * self.average_crit_multiplier()
    
    def flat_weakpoint_dph(self) -> float:
        return (self.weapon.effective.total_damage * self.weapon.effective.multishot * self.weapon.effective.weakpoint_damage * self.average_weakpoint_crit_multiplier() + self.weapon.effective.explosion_total_damage * self.average_crit_multiplier()) * self.weapon.effective.faction_damage
    
    def flat_dps(self) -> float:
        return self.average_fire_rate() * self.flat_dph()
    
    def flat_weakpoint_dps(self) -> float:
        return self.average_fire_rate() * self.flat_weakpoint_dph()
    
    def flat_dotph(self) -> float:
        direct_damage = self._flat_dotph_for(self.weapon.effective.damage_dist, self.weapon.base.forced_procs, self.weapon.effective.crit_chance, self.average_crit_multiplier())
        explosion_damage = self._flat_dotph_for(self.weapon.effective.explosion_damage_dist, self.weapon.base.explosion_forced_procs, self.weapon.effective.crit_chance, self.average_crit_multiplier(), include_multishot=False)
        return direct_damage + explosion_damage
    
    def flat_weakpoint_dotph(self) -> float:
        direct_damage = self._flat_dotph_for(self.weapon.effective.damage_dist, self.weapon.base.forced_procs, self.weapon.effective.weakpoint_crit_chance, self.average_weakpoint_crit_multiplier())
        explosion_damage = self._flat_dotph_for(self.weapon.effective.explosion_damage_dist, self.weapon.base.explosion_forced_procs, self.weapon.effective.crit_chance, self.average_crit_multiplier(), include_multishot=False)
        return direct_damage + explosion_damage
    
    def flat_dotps(self) -> float:
        return self.average_fire_rate() * self.flat_dotph()
    
    def flat_weakpoint_dotps(self) -> float:
        return self.average_fire_rate() * self.flat_weakpoint_dotph()
    
    def total_weakpoint_dph(self) -> float:
        return self.flat_weakpoint_dph() + self.flat_weakpoint_dotph()
    
    def total_weakpoint_dps(self) -> float:
        return self.flat_weakpoint_dps() + self.flat_weakpoint_dotps()
    
    def _flat_dotph_for(self, damage_dist, forced_procs, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        raise NotImplementedError
