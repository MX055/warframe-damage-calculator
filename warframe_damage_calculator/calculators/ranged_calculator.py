from ..fields.attack_result import AttackResult
from ..utils.functions import clamp, true_round
from . import helpers
from .weapon_calculator import WeaponCalculator


class RangedCalculator(WeaponCalculator):
    def _compute_modded_stats(self, result: AttackResult) -> None:
        super()._compute_modded_stats(result)
        build, base, modded = result.build, result.base, result.modded

        modded.weakpoint_damage = max(base.weakpoint_damage + build.weakpoint_damage, 1)
        modded.multiplicative_fire_rate = 1 if build.fire_rate_lock else max(1 + build.multiplicative_fire_rate, 1)
        modded.fire_rate = max(base.fire_rate * (1 if build.fire_rate_lock else (1 + build.fire_rate)), 0.05)
        modded.burst_count = max(base.burst_count, 1)
        modded.burst_delay = max(base.burst_delay, 0) / (1 if build.fire_rate_lock else max(1 + build.fire_rate, 1))
        modded.charge_time = max(base.charge_time, 0) / (1 if build.fire_rate_lock else max(1 + build.fire_rate, 0.01))
        modded.reload_speed = max(base.reload_speed, 0) / max(1 + build.reload_speed, 0.01)
        modded.recharge_rate = max(base.recharge_rate, 0)
        modded.ammo_cost = max(base.ammo_cost, 0)
        modded.ammo_efficiency = clamp(build.ammo_efficiency, 0, 1)
        modded.magazine_capacity = max(true_round(base.magazine_capacity * (1 + build.magazine_capacity)), 1)
        modded.multishot = max(base.multishot * (1 if build.multishot_lock else (1 + build.multishot)), 1)
        modded.multiplicative_weakpoint_crit_chance = max(1 + build.multiplicative_weakpoint_crit_chance, 1)
        modded.weakpoint_crit_chance = max(base.crit_chance * (1 + build.crit_chance + build.weakpoint_crit_chance), 0)
        modded.internal_bleeding = max(build.internal_bleeding * (2 if modded.fire_rate * modded.multiplicative_fire_rate < 2.5 else 1), 0)

    def _compute_effective_stats(self, result: AttackResult) -> None:
        super()._compute_effective_stats(result)
        modded, effective = result.modded, result.effective
        is_battery = "recharge_delay" in self.weapon.data.ammo

        effective.weakpoint_damage = modded.weakpoint_damage
        effective.fire_rate = modded.fire_rate * modded.multiplicative_fire_rate
        effective.burst_count = modded.burst_count
        effective.burst_delay = modded.burst_delay
        effective.charge_time = modded.charge_time / modded.multiplicative_fire_rate
        effective.reload_speed = modded.reload_speed + (0 if not is_battery else float("inf") if modded.recharge_rate <= 0 else modded.magazine_capacity / modded.recharge_rate)
        effective.recharge_rate = modded.recharge_rate
        effective.ammo_cost = modded.ammo_cost
        effective.ammo_efficiency = modded.ammo_efficiency
        effective.magazine_capacity = modded.magazine_capacity
        effective.multishot = modded.multishot
        effective.weakpoint_crit_chance = modded.weakpoint_crit_chance * (modded.multiplicative_crit_chance + modded.multiplicative_weakpoint_crit_chance - 1) + modded.flat_crit_chance
        effective.internal_bleeding = modded.internal_bleeding

    def _setup_ranged_averages(self, result: AttackResult) -> None:
        effective, average = result.effective, result.average
        average.weakpoint_crit_chance = effective.weakpoint_crit_chance
        average.weakpoint_crit_multiplier = helpers.crit_multiplier(average.weakpoint_crit_chance, effective.crit_damage)
        average.fire_rate = self._effective_attacks_per_second(result)
        average.procs_per_shot = effective.status_chance * effective.multishot

    def _apply_ranged_damage_averages(self, result: AttackResult) -> None:
        effective, average = result.effective, result.average
        average.flat_dph = effective.damage.total_damage() * effective.multishot * self._max_average_faction_damage(result) * average.crit_multiplier
        average.flat_weakpoint_dph = effective.damage.total_damage() * effective.multishot * effective.weakpoint_damage * average.weakpoint_crit_multiplier * self._max_average_faction_damage(result)
        average.flat_dotph = self._flat_dotph(result)
        average.flat_weakpoint_dotph = self._flat_dotph(result, weakpoint=True)
        average.flat_dotps = average.fire_rate * average.flat_dotph
        average.flat_weakpoint_dotps = average.fire_rate * average.flat_weakpoint_dotph
        helpers.refresh_dps_from_dph(average)

    def _compute_average_stats(self, result: AttackResult) -> None:
        super()._compute_average_stats(result)
        self._setup_ranged_averages(result)
        self._apply_ranged_damage_averages(result)
