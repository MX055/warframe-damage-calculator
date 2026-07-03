from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from .weapon_calculator import WeaponCalculator

if TYPE_CHECKING:
    from ..models import RangedState
    from ..models import Ranged


class RangedCalculator(WeaponCalculator):
    def __init__(self, weapon: Ranged[RangedState]) -> None:
        self.weapon: Ranged[RangedState] = weapon

    @cached_property
    def average_weakpoint_crit_chance(self) -> float:
        return self.weapon.effective.weakpoint_crit_chance

    @cached_property
    def average_fire_rate(self) -> float:
        return self.weapon.effective.magazine_capacity / (self.weapon.effective.magazine_capacity / self.weapon.effective.burst_count * (self.weapon.effective.charge_time + (self.weapon.effective.burst_count - 1) * self.weapon.effective.burst_delay) + (self.weapon.effective.magazine_capacity / self.weapon.effective.burst_count - (1 - self.weapon.effective.ammo_efficiency)) / self.weapon.effective.fire_rate + (1 - self.weapon.effective.ammo_efficiency) * self.weapon.effective.reload_speed)

    @cached_property
    def average_procs_per_shot(self) -> float:
        return self.weapon.effective.status_chance * self.weapon.effective.multishot

    @cached_property
    def average_weakpoint_crit_multiplier(self) -> float:
        return 1 + self.weapon.effective.weakpoint_crit_chance * (self.weapon.effective.crit_damage - 1)
    
    @cached_property
    def beam_dot_multiplier(self) -> float:
        return self.weapon.effective.multishot if self.weapon.effective.is_beam else 1

    @cached_property
    def flat_dph(self) -> float:
        return (self.weapon.effective.total_damage * self.weapon.effective.multishot + self.weapon.effective.explosion_total_damage) * self.weapon.effective.faction_damage * self.average_crit_multiplier

    @cached_property
    def flat_weakpoint_dph(self) -> float:
        return (self.weapon.effective.total_damage * self.weapon.effective.multishot * self.weapon.effective.weakpoint_damage * self.average_weakpoint_crit_multiplier + self.weapon.effective.explosion_total_damage * self.average_crit_multiplier) * self.weapon.effective.faction_damage

    @cached_property
    def flat_dps(self) -> float:
        return self.average_fire_rate * self.flat_dph

    @cached_property
    def flat_weakpoint_dps(self) -> float:
        return self.average_fire_rate * self.flat_weakpoint_dph

    @cached_property
    def flat_dotph(self) -> float:
        direct_damage = self._flat_dotph_for(self.weapon.effective.damage_dist, self.weapon.base.forced_procs, self.weapon.effective.crit_chance, self.average_crit_multiplier)
        explosion_damage = self._flat_dotph_for(self.weapon.effective.explosion_damage_dist, self.weapon.base.explosion_forced_procs, self.weapon.effective.crit_chance, self.average_crit_multiplier, include_multishot=False)
        return direct_damage + explosion_damage

    @cached_property
    def flat_weakpoint_dotph(self) -> float:
        direct_damage = self._flat_dotph_for(self.weapon.effective.damage_dist, self.weapon.base.forced_procs, self.weapon.effective.weakpoint_crit_chance, self.average_weakpoint_crit_multiplier)
        explosion_damage = self._flat_dotph_for(self.weapon.effective.explosion_damage_dist, self.weapon.base.explosion_forced_procs, self.weapon.effective.crit_chance, self.average_crit_multiplier, include_multishot=False)
        return direct_damage + explosion_damage

    @cached_property
    def flat_dotps(self) -> float:
        return self.average_fire_rate * self.flat_dotph

    @cached_property
    def flat_weakpoint_dotps(self) -> float:
        return self.average_fire_rate * self.flat_weakpoint_dotph

    @cached_property
    def total_weakpoint_dph(self) -> float:
        return self.flat_weakpoint_dph + self.flat_weakpoint_dotph

    @cached_property
    def total_weakpoint_dps(self) -> float:
        return self.flat_weakpoint_dps + self.flat_weakpoint_dotps
    
    def _flat_dotph_for(self, damage_dist, forced_procs, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        return NotImplemented
