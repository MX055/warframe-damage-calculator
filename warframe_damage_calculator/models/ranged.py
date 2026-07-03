from __future__ import annotations

from ..calculators import RangedCalculator
from .. formatters import RangedFormatter
from ..utils import true_round, clamp
from .states import RangedState
from .weapon import Weapon


class Ranged[TRangedState: RangedState, TRangedCalculator: RangedCalculator, TRangedFormatter: RangedFormatter](Weapon[TRangedState, TRangedCalculator, TRangedFormatter]):
    def __init__(self, base: TRangedState) -> None:
        super().__init__(base)
        self.base.explosion_total_damage = self.base.explosion_damage_dist.total_damage

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.is_beam = self.base.is_beam
        self.moded.is_battery = self.base.is_battery
        self.moded.explosion_damage_dist = self.moded.base_damage * self.base.explosion_damage_dist.apply(self.build.damage_dist).combine()
        self.moded.explosion_total_damage = self.moded.explosion_damage_dist.total_damage
        self.moded.weakpoint_damage = max(self.base.weakpoint_damage + self.build.weakpoint_damage, 1)
        self.moded.multiplicative_fire_rate = max(1 + self.build.multiplicative_fire_rate, 1)
        self.moded.fire_rate = max(self.base.fire_rate * (1 + self.build.fire_rate), 0.05)
        self.moded.burst_count = max(self.base.burst_count, 1)
        self.moded.burst_delay = max(self.base.burst_delay, 0) / max(1 + self.build.fire_rate, 1)
        self.moded.charge_time = max(self.base.charge_time, 0) / max(1 + self.build.fire_rate, 0.01)
        self.moded.reload_speed = max(self.base.reload_speed, 0) / max(1 + self.build.reload_speed, 0.01)
        self.moded.recharge_rate = max(self.base.recharge_rate, 0)
        self.moded.ammo_efficiency = clamp(self.build.ammo_efficiency, 0, 1)
        self.moded.magazine_capacity = max(true_round(self.base.magazine_capacity * (1 + self.build.magazine_capacity)), 1)
        self.moded.multishot = max(self.base.multishot * (1 + self.build.multishot), 1)
        self.moded.multiplicative_weakpoint_crit_chance = max(1 + self.build.multiplicative_weakpoint_crit_chance, 1)
        self.moded.weakpoint_crit_chance = max(self.base.crit_chance * (1 + self.build.crit_chance + self.build.weakpoint_crit_chance), 0)
        self.moded.internal_bleeding = max(self.build.internal_bleeding * (2 if self.moded.fire_rate * self.moded.multiplicative_fire_rate < 2.5 else 1), 0)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.is_beam = self.moded.is_beam
        self.effective.is_battery = self.effective.is_battery
        self.effective.explosion_damage_dist = self.moded.explosion_damage_dist
        self.effective.explosion_total_damage = self.effective.explosion_damage_dist.total_damage
        self.effective.weakpoint_damage = self.moded.weakpoint_damage
        self.effective.fire_rate = self.moded.fire_rate * self.moded.multiplicative_fire_rate
        self.effective.burst_count = self.moded.burst_count
        self.effective.burst_delay = self.moded.burst_delay
        self.effective.charge_time = self.moded.charge_time / self.moded.multiplicative_fire_rate
        self.effective.reload_speed = self.moded.reload_speed + (self.moded.magazine_capacity / self.moded.recharge_rate if self.effective.is_battery else 0)
        self.effective.recharge_rate = self.moded.recharge_rate
        self.effective.ammo_efficiency = 1 - (1 - self.moded.ammo_efficiency) / (2 if self.effective.is_beam else 1)
        self.effective.magazine_capacity = self.moded.magazine_capacity
        self.effective.multishot = self.moded.multishot
        self.effective.weakpoint_crit_chance = self.moded.weakpoint_crit_chance * (self.moded.multiplicative_crit_chance + self.moded.multiplicative_weakpoint_crit_chance - 1) + self.moded.flat_crit_chance
        self.effective.internal_bleeding = self.moded.internal_bleeding

