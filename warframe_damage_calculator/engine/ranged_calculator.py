from ..fields.attack_result import AttackResult
from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp, true_round
from ..utils.types import Number
from . import application_chance, damage, formulas, target
from .magazine_position import apply_magazine_position_mixture
from .weapon_calculator import WeaponCalculator


class RangedCalculator(WeaponCalculator):
    @staticmethod
    def _fire_rate_scale(result: AttackResult, *, floor: float | None = 0.01) -> float:
        build, evo = result.build, result.evolutions
        if build.proportional.fire_rate_lock: return 1.0
        scale = 1 + build.proportional.fire_rate + evo.proportional.fire_rate
        return scale if floor is None else max(scale, floor)

    @staticmethod
    def _fire_rate_factor(result: AttackResult) -> float:
        build, evo = result.build, result.evolutions
        if build.proportional.fire_rate_lock: return 1.0
        return formulas.fold_multiplicative_families(build, evo, stat="fire_rate")

    def _battery_reload_time(self, result: AttackResult) -> float:
        modded = result.modded
        if "recharge_delay" not in self.weapon.data.ammo: return 0.0
        if modded.proportional.recharge_rate <= 0: return float("inf")
        return modded.proportional.magazine_capacity / modded.proportional.recharge_rate

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded
        is_incarnon = (result.attack.form or "normal") == "incarnon"
        modded.proportional.weakpoint_damage = max(base.weakpoint_damage + build.proportional.weakpoint_damage + evo.proportional.weakpoint_damage, 1)
        modded.proportional.fire_rate = max(base.fire_rate * self._fire_rate_scale(result, floor=None), 0.05)
        modded.proportional.burst_count = max(base.burst_count, 1)
        modded.proportional.burst_delay = max(base.burst_delay, 0) / self._fire_rate_scale(result, floor=1)
        modded.proportional.charge_time = max(base.charge_time, 0) / self._fire_rate_scale(result)
        modded.proportional.reload_speed = max(base.reload_speed, 0) / max(1 + build.proportional.reload_speed + evo.proportional.reload_speed, 0.01)
        modded.proportional.recharge_rate = max(base.recharge_rate, 0)
        modded.proportional.ammo_cost = max(base.ammo_cost, 0)
        # Incarnon charge pools ignore magazine mods and ammo efficiency.
        if is_incarnon:
            modded.proportional.ammo_efficiency = 0
            modded.proportional.magazine_capacity = max(true_round(base.magazine_capacity), 1)
        else:
            modded.proportional.ammo_efficiency = clamp(build.proportional.ammo_efficiency + evo.proportional.ammo_efficiency, 0, 1)
            modded.proportional.magazine_capacity = max(true_round(base.magazine_capacity * (1 + build.proportional.magazine_capacity + evo.proportional.magazine_capacity)), 1)
        ms_bonus = 0.0 if build.proportional.multishot_lock else (build.proportional.multishot + evo.proportional.multishot)
        ms_ammo_bonus = formulas.multishot_consumes_ammo_bonus(build, evo)
        # Beam Incarnon perks boost all multishot bonuses instead of per-pellet unique damage.
        if ms_ammo_bonus and result.attack.delivery == "beam" and not build.proportional.multishot_lock:
            ms_bonus *= 1 + ms_ammo_bonus
        modded.proportional.multishot = max(base.multishot * (1 + ms_bonus), 1)
        modded.proportional.weakpoint_crit_chance = max(base.crit_chance * (1 + build.proportional.crit_chance + build.proportional.weakpoint_crit_chance), 0)
        modded.proportional.projectile_speed = build.proportional.projectile_speed + evo.proportional.projectile_speed
        modded.proportional.start_range = float(base.start_range or 0) * (1 + float(modded.proportional.projectile_speed or 0))
        modded.proportional.end_range = float(base.end_range or 0) * (1 + float(modded.proportional.projectile_speed or 0))
        modded.proportional.final_multiplier = base.final_multiplier or 1
        modded.proportional.accuracy = base.accuracy * (1 + build.proportional.accuracy + evo.proportional.accuracy) + build.flat.accuracy + evo.flat.accuracy if base.accuracy else build.proportional.accuracy + evo.proportional.accuracy + build.flat.accuracy + evo.flat.accuracy
        modded.proportional.zoom = base.zoom * (1 + build.proportional.zoom + evo.proportional.zoom) + build.flat.zoom + evo.flat.zoom if base.zoom else build.proportional.zoom + evo.proportional.zoom + build.flat.zoom + evo.flat.zoom
        modded.proportional.recoil = base.recoil * (1 + build.proportional.recoil + evo.proportional.recoil) + build.flat.recoil + evo.flat.recoil if base.recoil else build.proportional.recoil + evo.proportional.recoil + build.flat.recoil + evo.flat.recoil
        modded.proportional.ammo_maximum = max(base.ammo_maximum * (1 + build.proportional.ammo_maximum + evo.proportional.ammo_maximum) + build.flat.ammo_maximum + evo.flat.ammo_maximum, 0)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        modded, effective = result.modded, result.effective
        fire_rate_factor = self._fire_rate_factor(result)
        crit_factor = formulas.fold_multiplicative_families(result.build, result.evolutions, stat="crit_chance")
        weakpoint_crit_factor = formulas.fold_multiplicative_families(result.build, result.evolutions, stat="weakpoint_crit_chance")
        effective.weakpoint_damage = modded.proportional.weakpoint_damage
        effective.fire_rate = modded.proportional.fire_rate * fire_rate_factor
        effective.burst_count = modded.proportional.burst_count
        effective.burst_delay = modded.proportional.burst_delay
        effective.charge_time = modded.proportional.charge_time / fire_rate_factor
        effective.reload_speed = modded.proportional.reload_speed + self._battery_reload_time(result)
        effective.recharge_rate = modded.proportional.recharge_rate
        ms_ammo_enabled = formulas.multishot_consumes_ammo_enabled(result.build, result.evolutions)
        ms_ammo_bonus = formulas.multishot_consumes_ammo_bonus(result.build, result.evolutions)
        effective.multishot = modded.proportional.multishot
        effective.ammo_cost = formulas.multishot_ammo_cost(modded.proportional.ammo_cost, effective.multishot, enabled=ms_ammo_enabled)
        effective.ammo_efficiency = modded.proportional.ammo_efficiency
        effective.magazine_capacity = modded.proportional.magazine_capacity
        effective.ammo_maximum = modded.proportional.ammo_maximum
        # Crit and weakpoint family bonuses stack their excesses (1+c)+(1+w)-1, matching Primary Acuity.
        effective.weakpoint_crit_chance = formulas.combine_chance(modded.proportional.weakpoint_crit_chance, crit_factor + weakpoint_crit_factor - 1, modded.flat.crit_chance)
        effective.projectile_speed = modded.proportional.projectile_speed
        effective.start_range = modded.proportional.start_range
        effective.end_range = modded.proportional.end_range
        effective.final_multiplier = modded.proportional.final_multiplier
        effective.accuracy = modded.proportional.accuracy
        effective.zoom = modded.proportional.zoom
        effective.recoil = modded.proportional.recoil
        # Unique MS-ammo damage applies only to multishot-generated pellets (non-beam).
        if ms_ammo_enabled and result.attack.delivery != "beam" and ms_ammo_bonus:
            effective.damage = effective.damage * formulas.multishot_ammo_damage_factor(effective.multishot, ms_ammo_bonus)

    def _sustained_attack_rate(self, result: AttackResult) -> float:
        """Magazine-cycle sustained fire rate used for status/CO and average DPS."""
        stats, modded = result.attack.stats, result.modded
        if "magazine_capacity" not in modded.proportional: return super()._sustained_attack_rate(result)

        speed = self._fire_rate_scale(result)
        fire_rate_factor = self._fire_rate_factor(result)
        fire_rate = max(stats.fire_rate * speed, 0.05) * fire_rate_factor
        burst_count = max(stats.burst_count, 1)
        ammo_cost = formulas.multishot_ammo_cost(
            modded.proportional.ammo_cost,
            modded.proportional.multishot,
            enabled=formulas.multishot_consumes_ammo_enabled(result.build, result.evolutions),
        )
        if ammo_cost <= 0: return fire_rate
        shots = modded.proportional.magazine_capacity / ammo_cost
        bursts = shots / burst_count
        reload_speed = modded.proportional.reload_speed + self._battery_reload_time(result)
        ammo_spent = 1 - modded.proportional.ammo_efficiency
        charge_time = max(stats.charge_time, 0) / speed / fire_rate_factor
        burst_delay = (burst_count - 1) * max(stats.burst_delay, 0) / max(speed, 1)
        cycle = bursts * (charge_time + burst_delay)
        cycle += (bursts - ammo_spent) / fire_rate + ammo_spent * reload_speed
        return float("inf") if cycle <= 0 else shots / cycle

    def _slash_dot_factor(self, result: AttackResult) -> float:
        return dict(DOT_MULTIPLIERS)["slash"] * result.effective.status_duration

    def _impact_weight(self, result: AttackResult) -> float:
        return result.effective.damage.weight("impact") + result.base.forced_procs.get("impact")

    def _internal_bleeding_chance(self, result: AttackResult) -> float:
        chance = application_chance.internal_bleeding_chance(result.build.application_chance)
        threshold = application_chance.internal_bleeding_threshold(result.build.application_chance)
        if result.effective.fire_rate < threshold: chance *= 2
        return max(chance, 0)

    def _ib_slash_dot_per_proc(self, result: AttackResult, *, hit_multiplier: Number, faction_damage: Number, damage_multiplier: Number = 1, weakpoint: bool = False, resistant: bool = False) -> float:
        zone = "weakpoint" if weakpoint else "resistant" if resistant else "normal"
        slash_target = target.damage_type_multiplier(self.weapon.target, "slash", dot=True, status_effects=result.status_effects, zone=zone, weakpoint_bonus=self._weakpoint_damage_bonus(result))
        return self._slash_dot_factor(result) * result.effective.damage.total_damage() * hit_multiplier * result.effective.status_damage * faction_damage ** 2 * damage_multiplier * slash_target

    def _average_crit_chances(self, result: AttackResult) -> tuple[float, float]:
        """Authoritative average crit chances for body and weakpoint hits."""
        effective = result.effective
        return float(effective.crit_chance), float(effective.weakpoint_crit_chance)

    def _weakpoint_damage_bonus(self, result: AttackResult) -> float:
        return max(float(result.effective.weakpoint_damage) - float(result.base.weakpoint_damage), 0)

    def _direct_damage(self, result: AttackResult, zone="normal") -> float:
        if self.weapon.target is None:
            damage = float(result.effective.damage.total_damage())
            return damage * float(result.effective.weakpoint_damage) if zone == "weakpoint" else damage if zone == "normal" else 0.0
        return super()._direct_damage(result, zone)

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

        hit_mult = formulas.hit_multiplier(crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        weakpoint_hit_mult = formulas.hit_multiplier(weakpoint_crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        faction = self._max_average_faction_damage(result)
        scale = effective.multishot * faction
        for key, value in damage.zone_dph_metrics(compute_direct=lambda zone="normal": self._direct_damage(result, zone), compute_dotph=lambda **kwargs: self._flat_dotph(result, **kwargs), normal_scale=scale * hit_mult, weakpoint_scale=scale * weakpoint_hit_mult, resistant_scale=scale * hit_mult).items():
            average[key] = value
        formulas.refresh_dps_from_dph(average)
        apply_magazine_position_mixture(result, compute_dotph=self._flat_dotph, compute_direct=self._direct_damage, faction_damage=faction)
