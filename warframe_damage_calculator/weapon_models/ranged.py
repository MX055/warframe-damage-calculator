from __future__ import annotations

from ..mechanics import RangedState, true_round, clamp
from ..calculators import RangedCalculator
from ..formatters import RangedFormatter
from .weapon import Weapon


class Ranged[TWeaponState: RangedState](Weapon[TWeaponState]):
    _calculator_class = RangedCalculator
    _formatter_class = RangedFormatter

    def __init__(self, base: TWeaponState) -> None:
        super().__init__(base)
        self.base.explosion_total_damage = self.base.explosion_damage_dist.total_damage

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.explosion_damage_dist = self.moded.base_damage * self.base.explosion_damage_dist.apply(self.build.damage_dist).combine()
        self.moded.explosion_total_damage = self.moded.explosion_damage_dist.total_damage
        self.moded.weakpoint_damage = max(self.base.weakpoint_damage + self.build.weakpoint_damage, 1)
        self.moded.multiplicative_fire_rate = max(1 + self.build.multiplicative_fire_rate, 1)
        self.moded.fire_rate = max(self.base.fire_rate * (1 + self.build.fire_rate), 0.05)
        self.moded.charge_time = self.base.charge_time / max(1 + self.build.fire_rate, 0.01)
        self.moded.reload_speed = self.base.reload_speed / max(1 + self.build.reload_speed, 0.01)
        self.moded.magazine_capacity = max(true_round(self.base.magazine_capacity * (1 + self.build.magazine_capacity)), 1)
        self.moded.ammo_efficiency = clamp(self.build.ammo_efficiency, 0, 1)
        self.moded.multishot = max(self.base.multishot * (1 + self.build.multishot), 1)
        self.moded.multiplicative_weakpoint_crit_chance = max(1 + self.build.multiplicative_weakpoint_crit_chance, 1)
        self.moded.weakpoint_crit_chance = max(self.base.crit_chance * (1 + self.build.crit_chance + self.build.weakpoint_crit_chance), 0)
        self.moded.internal_bleeding = max(self.build.internal_bleeding * (2 if max(self.moded.fire_rate * self.moded.multiplicative_fire_rate, 0.05) < 2.5 else 1), 0)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.explosion_damage_dist = self.moded.explosion_damage_dist
        self.effective.explosion_total_damage = self.effective.explosion_damage_dist.total_damage
        self.effective.weakpoint_damage = self.moded.weakpoint_damage
        self.effective.fire_rate = self.moded.fire_rate * self.moded.multiplicative_fire_rate
        self.effective.charge_time = self.moded.charge_time
        self.effective.reload_speed = self.moded.reload_speed
        self.effective.magazine_capacity = self.moded.magazine_capacity
        self.effective.multishot = self.moded.multishot
        self.effective.weakpoint_crit_chance = self.moded.weakpoint_crit_chance * (self.moded.multiplicative_crit_chance + self.moded.multiplicative_weakpoint_crit_chance - 1) + self.moded.flat_crit_chance
        self.effective.internal_bleeding = self.moded.internal_bleeding