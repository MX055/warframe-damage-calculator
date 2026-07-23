from ..fields.attack_result import AttackResult
from ..utils.functions import clamp, true_round
from .weapon_calculator import WeaponCalculator


class RangedCalculator(WeaponCalculator):
    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded

        modded.additive.weakpoint_damage = max(base.weakpoint_damage + build.additive.weakpoint_damage + evo.additive.weakpoint_damage, 1)
        modded.multiplicative.fire_rate = 1 if build.additive.fire_rate_lock else max(1 + build.multiplicative.fire_rate + evo.multiplicative.fire_rate, 1)
        modded.additive.fire_rate = max(base.fire_rate * (1 if build.additive.fire_rate_lock else (1 + build.additive.fire_rate + evo.additive.fire_rate)), 0.05)
        modded.additive.burst_count = max(base.burst_count, 1)
        modded.additive.burst_delay = max(base.burst_delay, 0) / (1 if build.additive.fire_rate_lock else max(1 + build.additive.fire_rate + evo.additive.fire_rate, 1))
        modded.additive.charge_time = max(base.charge_time, 0) / (1 if build.additive.fire_rate_lock else max(1 + build.additive.fire_rate + evo.additive.fire_rate, 0.01))
        modded.additive.reload_speed = max(base.reload_speed, 0) / max(1 + build.additive.reload_speed + evo.additive.reload_speed, 0.01)
        modded.additive.recharge_rate = max(base.recharge_rate, 0)
        modded.additive.ammo_cost = max(base.ammo_cost, 0)
        modded.additive.ammo_efficiency = clamp(build.additive.ammo_efficiency + evo.additive.ammo_efficiency, 0, 1)
        modded.additive.magazine_capacity = max(true_round(base.magazine_capacity * (1 + build.additive.magazine_capacity + evo.additive.magazine_capacity)), 1)
        modded.additive.multishot = max(base.multishot * (1 if build.additive.multishot_lock else (1 + build.additive.multishot + evo.additive.multishot)), 1)
        modded.multiplicative.weakpoint_crit_chance = max(1 + build.multiplicative.weakpoint_crit_chance, 1)
        modded.additive.weakpoint_crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance + build.additive.weakpoint_crit_chance), 0)
        modded.additive.internal_bleeding = max(build.additive.internal_bleeding * (2 if modded.additive.fire_rate * modded.multiplicative.fire_rate < 2.5 else 1), 0)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        modded, effective = result.modded, result.effective
        is_battery = "recharge_delay" in self.weapon.data.ammo

        effective.weakpoint_damage = modded.additive.weakpoint_damage
        effective.fire_rate = modded.additive.fire_rate * modded.multiplicative.fire_rate
        effective.burst_count = modded.additive.burst_count
        effective.burst_delay = modded.additive.burst_delay
        effective.charge_time = modded.additive.charge_time / modded.multiplicative.fire_rate
        effective.reload_speed = modded.additive.reload_speed + (0 if not is_battery else float("inf") if modded.additive.recharge_rate <= 0 else modded.additive.magazine_capacity / modded.additive.recharge_rate)
        effective.recharge_rate = modded.additive.recharge_rate
        effective.ammo_cost = modded.additive.ammo_cost
        effective.ammo_efficiency = modded.additive.ammo_efficiency
        effective.magazine_capacity = modded.additive.magazine_capacity
        effective.multishot = modded.additive.multishot
        effective.weakpoint_crit_chance = self._combine_chance(modded.additive.weakpoint_crit_chance, modded.multiplicative.crit_chance + modded.multiplicative.weakpoint_crit_chance - 1, modded.flat.crit_chance)
        effective.internal_bleeding = modded.additive.internal_bleeding

    def _setup_ranged_averages(self, result: AttackResult) -> None:
        effective, average = result.effective, result.average
        average.weakpoint_crit_chance = effective.weakpoint_crit_chance
        average.weakpoint_crit_multiplier = self._crit_multiplier(average.weakpoint_crit_chance, effective.crit_damage)
        average.fire_rate = self._effective_attacks_per_second(result)
        average.procs_per_shot = effective.status_chance * effective.multishot

    def _apply_ranged_damage_averages(self, result: AttackResult) -> None:
        effective, average = result.effective, result.average
        hit_mult = self._hit_multiplier(average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        weakpoint_hit_mult = self._hit_multiplier(average.weakpoint_crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        average.flat_dph = effective.damage.total_damage() * effective.multishot * self._max_average_faction_damage(result) * hit_mult
        average.flat_weakpoint_dph = effective.damage.total_damage() * effective.multishot * effective.weakpoint_damage * weakpoint_hit_mult * self._max_average_faction_damage(result)
        average.flat_dotph = self._flat_dotph(result)
        average.flat_weakpoint_dotph = self._flat_dotph(result, weakpoint=True)
        average.flat_dotps = average.fire_rate * average.flat_dotph
        average.flat_weakpoint_dotps = average.fire_rate * average.flat_weakpoint_dotph
        self._refresh_dps_from_dph(average)

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        self._setup_ranged_averages(result)
        self._apply_ranged_damage_averages(result)
