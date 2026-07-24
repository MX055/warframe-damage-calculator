from ..fields.attack_result import AttackResult
from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp, true_round
from ..utils.types import Number
from . import formulas
from .weapon_calculator import WeaponCalculator


class RangedCalculator(WeaponCalculator):
    @staticmethod
    def _fire_rate_scale(result: AttackResult, *, floor: float | None = 0.01) -> float:
        build, evo = result.build, result.evolutions
        if build.additive.fire_rate_lock: return 1.0
        scale = 1 + build.additive.fire_rate + evo.additive.fire_rate
        return scale if floor is None else max(scale, floor)

    def _battery_reload_time(self, result: AttackResult) -> float:
        modded = result.modded
        if "recharge_delay" not in self.weapon.data.ammo: return 0.0
        if modded.additive.recharge_rate <= 0: return float("inf")
        return modded.additive.magazine_capacity / modded.additive.recharge_rate

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded
        modded.additive.weakpoint_damage = max(base.weakpoint_damage + build.additive.weakpoint_damage + evo.additive.weakpoint_damage, 1)
        modded.multiplicative.fire_rate = 1 if build.additive.fire_rate_lock else max(1 + build.multiplicative.fire_rate + evo.multiplicative.fire_rate, 1)
        modded.additive.fire_rate = max(base.fire_rate * self._fire_rate_scale(result, floor=None), 0.05)
        modded.additive.burst_count = max(base.burst_count, 1)
        modded.additive.burst_delay = max(base.burst_delay, 0) / self._fire_rate_scale(result, floor=1)
        modded.additive.charge_time = max(base.charge_time, 0) / self._fire_rate_scale(result)
        modded.additive.reload_speed = max(base.reload_speed, 0) / max(1 + build.additive.reload_speed + evo.additive.reload_speed, 0.01)
        modded.additive.recharge_rate = max(base.recharge_rate, 0)
        modded.additive.ammo_cost = max(base.ammo_cost, 0)
        modded.additive.ammo_efficiency = clamp(build.additive.ammo_efficiency + evo.additive.ammo_efficiency, 0, 1)
        modded.additive.magazine_capacity = max(true_round(base.magazine_capacity * (1 + build.additive.magazine_capacity + evo.additive.magazine_capacity)), 1)
        modded.additive.multishot = max(base.multishot * (1 if build.additive.multishot_lock else (1 + build.additive.multishot + evo.additive.multishot)), 1)
        modded.multiplicative.weakpoint_crit_chance = max(1 + build.multiplicative.weakpoint_crit_chance, 1)
        modded.additive.weakpoint_crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance + build.additive.weakpoint_crit_chance), 0)
        modded.additive.internal_bleeding = max(build.additive.internal_bleeding * (2 if modded.additive.fire_rate * modded.multiplicative.fire_rate < 2.5 else 1), 0)
        modded.additive.projectile_speed = build.additive.projectile_speed + evo.additive.projectile_speed
        modded.additive.start_range = float(base.get("start_range", 0) or 0) * (1 + float(modded.additive.projectile_speed or 0))
        modded.additive.end_range = float(base.get("end_range", 0) or 0) * (1 + float(modded.additive.projectile_speed or 0))
        modded.additive.final_multiplier = base.get("final_multiplier", 1) or 1

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        modded, effective = result.modded, result.effective
        effective.weakpoint_damage = modded.additive.weakpoint_damage
        effective.fire_rate = modded.additive.fire_rate * modded.multiplicative.fire_rate
        effective.burst_count = modded.additive.burst_count
        effective.burst_delay = modded.additive.burst_delay
        effective.charge_time = modded.additive.charge_time / modded.multiplicative.fire_rate
        effective.reload_speed = modded.additive.reload_speed + self._battery_reload_time(result)
        effective.recharge_rate = modded.additive.recharge_rate
        effective.ammo_cost = modded.additive.ammo_cost
        effective.ammo_efficiency = modded.additive.ammo_efficiency
        effective.magazine_capacity = modded.additive.magazine_capacity
        effective.multishot = modded.additive.multishot
        effective.weakpoint_crit_chance = formulas.combine_chance(modded.additive.weakpoint_crit_chance, modded.multiplicative.crit_chance + modded.multiplicative.weakpoint_crit_chance - 1, modded.flat.crit_chance)
        effective.internal_bleeding = modded.additive.internal_bleeding
        effective.projectile_speed = modded.additive.projectile_speed
        effective.start_range = modded.additive.start_range
        effective.end_range = modded.additive.end_range
        effective.final_multiplier = modded.additive.final_multiplier

    def _sustained_attack_rate(self, result: AttackResult) -> float:
        """Magazine-cycle sustained fire rate used for status/CO and average DPS."""
        stats, modded = result.attack.stats, result.modded
        if "magazine_capacity" not in modded.additive: return super()._sustained_attack_rate(result)

        speed = self._fire_rate_scale(result)
        fire_rate = max(stats.fire_rate * speed, 0.05) * modded.multiplicative.fire_rate
        burst_count = max(stats.burst_count, 1)
        ammo_cost = max(float(modded.additive.get("ammo_cost", stats.ammo_cost)), 0)
        if ammo_cost <= 0: return fire_rate
        shots = modded.additive.magazine_capacity / ammo_cost
        bursts = shots / burst_count
        reload_speed = modded.additive.reload_speed + self._battery_reload_time(result)
        ammo_spent = 1 - modded.additive.ammo_efficiency
        charge_time = max(stats.charge_time, 0) / speed / modded.multiplicative.fire_rate
        burst_delay = (burst_count - 1) * max(stats.burst_delay, 0) / max(speed, 1)
        cycle = bursts * (charge_time + burst_delay)
        cycle += (bursts - ammo_spent) / fire_rate + ammo_spent * reload_speed
        return float("inf") if cycle <= 0 else shots / cycle

    def _slash_dot_factor(self, result: AttackResult) -> float:
        return dict(DOT_MULTIPLIERS)["slash"] * result.effective.status_duration

    def _impact_weight(self, result: AttackResult) -> float:
        return result.effective.damage.weight("impact") + result.base.forced_procs.get("impact")

    def _ib_slash_dot_per_proc(self, result: AttackResult, *, hit_multiplier: Number, faction_damage: Number, damage_multiplier: Number = 1) -> float:
        return self._slash_dot_factor(result) * result.effective.damage.total_damage() * hit_multiplier * result.effective.status_damage * faction_damage ** 2 * damage_multiplier

    def _average_crit_chances(self, result: AttackResult) -> tuple[float, float]:
        """Authoritative average crit chances for body and weakpoint hits."""
        effective = result.effective
        return float(effective.crit_chance), float(effective.weakpoint_crit_chance)

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        effective, average = result.effective, result.average

        crit_chance, weakpoint_crit_chance = self._average_crit_chances(result)
        average.crit_chance = crit_chance
        average.weakpoint_crit_chance = weakpoint_crit_chance
        average.crit_multiplier = formulas.crit_multiplier(crit_chance, effective.crit_damage)
        average.weakpoint_crit_multiplier = formulas.crit_multiplier(weakpoint_crit_chance, effective.crit_damage)
        average.fire_rate = self._sustained_attack_rate(result)
        average.procs_per_shot = effective.status_chance * effective.multishot

        hit_mult = formulas.hit_multiplier(crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        weakpoint_hit_mult = formulas.hit_multiplier(weakpoint_crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        faction = self._max_average_faction_damage(result)
        average.flat_dph = effective.damage.total_damage() * effective.multishot * faction * hit_mult
        average.flat_weakpoint_dph = effective.damage.total_damage() * effective.multishot * effective.weakpoint_damage * weakpoint_hit_mult * faction
        average.flat_dotph = self._flat_dotph(result)
        average.flat_weakpoint_dotph = self._flat_dotph(result, weakpoint=True)
        average.flat_dotps = average.fire_rate * average.flat_dotph
        average.flat_weakpoint_dotps = average.fire_rate * average.flat_weakpoint_dotph
        formulas.refresh_dps_from_dph(average)
