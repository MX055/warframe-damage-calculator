from __future__ import annotations

from functools import cached_property

from ..utils import true_round, clamp
from ..states import RangedState
from ..models import dist
from .weapon_calculator import WeaponCalculator


class RangedCalculator[TRangedState: RangedState](WeaponCalculator[TRangedState]):
    def __init__(self, base: TRangedState) -> None:
        super().__init__(base)
        self.base.explosion_total_damage = self.base.explosion_damage_dist.total_damage()

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.is_beam = self.base.is_beam
        self.moded.is_battery = self.base.is_battery
        self.moded.explosion_damage_dist = self.moded.base_damage * self.base.explosion_damage_dist.apply(self._upgrade("damage_dist", dist())).combine().sorted()
        self.moded.explosion_total_damage = self.moded.explosion_damage_dist.total_damage()
        self.moded.weakpoint_damage = max(self.base.weakpoint_damage + self._upgrade("weakpoint_damage"), 1)
        self.moded.multiplicative_fire_rate = 1 if self._upgrade("fire_rate_lock", False) else max(1 + self._upgrade("multiplicative_fire_rate"), 1)
        self.moded.fire_rate = max(self.base.fire_rate * (1 if self._upgrade("fire_rate_lock", False) else (1 + self._upgrade("fire_rate"))), 0.05)
        self.moded.burst_count = max(self.base.burst_count, 1)
        self.moded.burst_delay = max(self.base.burst_delay, 0) / (1 if self._upgrade("fire_rate_lock", False) else max(1 + self._upgrade("fire_rate"), 1))
        self.moded.charge_time = max(self.base.charge_time, 0) / (1 if self._upgrade("fire_rate_lock", False) else max(1 + self._upgrade("fire_rate"), 0.01))
        self.moded.reload_speed = max(self.base.reload_speed, 0) / max(1 + self._upgrade("reload_speed"), 0.01)
        self.moded.recharge_rate = max(self.base.recharge_rate, 0)
        self.moded.ammo_efficiency = clamp(self._upgrade("ammo_efficiency"), 0, 1)
        self.moded.magazine_capacity = max(true_round(self.base.magazine_capacity * (1 + self._upgrade("magazine_capacity"))), 1)
        self.moded.multishot = max(self.base.multishot * (1 if self._upgrade("multishot_lock", False) else (1 + self._upgrade("multishot"))), 1)
        self.moded.multiplicative_weakpoint_crit_chance = max(1 + self._upgrade("multiplicative_weakpoint_crit_chance"), 1)
        self.moded.weakpoint_crit_chance = max(self.base.crit_chance * (1 + self._upgrade("crit_chance") + self._upgrade("weakpoint_crit_chance")), 0)
        self.moded.internal_bleeding = max(self._upgrade("internal_bleeding") * (2 if self.moded.fire_rate * self.moded.multiplicative_fire_rate < 2.5 else 1), 0)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.is_beam = self.moded.is_beam
        self.effective.is_battery = self.moded.is_battery
        self.effective.explosion_damage_dist = self.moded.explosion_damage_dist
        self.effective.explosion_total_damage = self.effective.explosion_damage_dist.total_damage()
        self.effective.weakpoint_damage = self.moded.weakpoint_damage
        self.effective.fire_rate = self.moded.fire_rate * self.moded.multiplicative_fire_rate
        self.effective.burst_count = self.moded.burst_count
        self.effective.burst_delay = self.moded.burst_delay
        self.effective.charge_time = self.moded.charge_time / self.moded.multiplicative_fire_rate
        self.effective.reload_speed = self.moded.reload_speed + (0 if not self.effective.is_battery else float("inf") if self.moded.recharge_rate <= 0 else self.moded.magazine_capacity / self.moded.recharge_rate)
        self.effective.recharge_rate = self.moded.recharge_rate
        self.effective.ammo_efficiency = 1 - (1 - self.moded.ammo_efficiency) / (2 if self.effective.is_beam else 1)
        self.effective.magazine_capacity = self.moded.magazine_capacity
        self.effective.multishot = self.moded.multishot
        self.effective.weakpoint_crit_chance = self.moded.weakpoint_crit_chance * (self.moded.multiplicative_crit_chance + self.moded.multiplicative_weakpoint_crit_chance - 1) + self.moded.flat_crit_chance
        self.effective.internal_bleeding = self.moded.internal_bleeding

    def _flat_dotph_for(self, damage_dist: dist, forced_procs: dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        raise NotImplementedError

    @cached_property
    def average_weakpoint_crit_chance(self) -> float:
        return self.effective.weakpoint_crit_chance

    @cached_property
    def average_fire_rate(self) -> float:
        cycle_time = self.effective.magazine_capacity / self.effective.burst_count * (self.effective.charge_time + (self.effective.burst_count - 1) * self.effective.burst_delay) + (self.effective.magazine_capacity / self.effective.burst_count - (1 - self.effective.ammo_efficiency)) / self.effective.fire_rate + (1 - self.effective.ammo_efficiency) * self.effective.reload_speed
        if cycle_time <= 0:
            return float("inf")
        return self.effective.magazine_capacity / cycle_time

    @cached_property
    def average_procs_per_shot(self) -> float:
        return self.effective.status_chance * self.effective.multishot

    @cached_property
    def average_weakpoint_crit_multiplier(self) -> float:
        return 1 + self.effective.weakpoint_crit_chance * (self.effective.crit_damage - 1)
    
    @cached_property
    def beam_dot_multiplier(self) -> float:
        return self.effective.multishot if self.effective.is_beam else 1

    @cached_property
    def flat_dph(self) -> float:
        return (self.effective.total_damage * self.effective.multishot + self.effective.explosion_total_damage) * self.effective.faction_damage * self.average_crit_multiplier

    @cached_property
    def flat_weakpoint_dph(self) -> float:
        return (self.effective.total_damage * self.effective.multishot * self.effective.weakpoint_damage * self.average_weakpoint_crit_multiplier + self.effective.explosion_total_damage * self.average_crit_multiplier) * self.effective.faction_damage

    @cached_property
    def flat_dps(self) -> float:
        return self.average_fire_rate * self.flat_dph

    @cached_property
    def flat_weakpoint_dps(self) -> float:
        return self.average_fire_rate * self.flat_weakpoint_dph

    @cached_property
    def flat_dotph(self) -> float:
        direct_damage = self._flat_dotph_for(self.effective.damage_dist, self.base.forced_procs, self.effective.crit_chance, self.average_crit_multiplier)
        explosion_damage = self._flat_dotph_for(self.effective.explosion_damage_dist, self.base.explosion_forced_procs, self.effective.crit_chance, self.average_crit_multiplier, include_multishot=False)
        return direct_damage + explosion_damage

    @cached_property
    def flat_weakpoint_dotph(self) -> float:
        direct_damage = self._flat_dotph_for(self.effective.damage_dist, self.base.forced_procs, self.effective.weakpoint_crit_chance, self.average_weakpoint_crit_multiplier)
        explosion_damage = self._flat_dotph_for(self.effective.explosion_damage_dist, self.base.explosion_forced_procs, self.effective.crit_chance, self.average_crit_multiplier, include_multishot=False)
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
