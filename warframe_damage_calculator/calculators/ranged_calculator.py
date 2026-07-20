from ..utils.functions import clamp, true_round
from ..utils.constants import DOT_MULTIPLIERS
from ..models.fields import CalculatedStats
from .weapon_calculator import WeaponCalculator


class RangedCalculator(WeaponCalculator):
    def _compute_modded_stats(self) -> None:
        super()._compute_modded_stats()
        build = self.build.stats.total
        
        self.modded.weakpoint_damage = max(self.base.weakpoint_damage + build.weakpoint_damage, 1)
        self.modded.multiplicative_fire_rate = 1 if build.fire_rate_lock else max(1 + build.multiplicative_fire_rate, 1)
        self.modded.fire_rate = max(self.base.fire_rate * (1 if build.fire_rate_lock else (1 + build.fire_rate)), 0.05)
        self.modded.burst_count = max(self.base.burst_count, 1)
        self.modded.burst_delay = max(self.base.burst_delay, 0) / (1 if build.fire_rate_lock else max(1 + build.fire_rate, 1))
        self.modded.charge_time = max(self.base.charge_time, 0) / (1 if build.fire_rate_lock else max(1 + build.fire_rate, 0.01))
        self.modded.reload_speed = max(self.base.reload_speed, 0) / max(1 + build.reload_speed, 0.01)
        self.modded.recharge_rate = max(self.base.recharge_rate, 0)
        self.modded.ammo_efficiency = clamp(build.ammo_efficiency, 0, 1)
        self.modded.magazine_capacity = max(true_round(self.base.magazine_capacity * (1 + build.magazine_capacity)), 1)
        self.modded.multishot = max(self.base.multishot * (1 if build.multishot_lock else (1 + build.multishot)), 1)
        self.modded.multiplicative_weakpoint_crit_chance = max(1 + build.multiplicative_weakpoint_crit_chance, 1)
        self.modded.weakpoint_crit_chance = max(self.base.crit_chance * (1 + build.crit_chance + build.weakpoint_crit_chance), 0)
        self.modded.internal_bleeding = max(build.internal_bleeding * (2 if self.modded.fire_rate * self.modded.multiplicative_fire_rate < 2.5 else 1), 0)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        is_battery = "recharge_delay" in self.weapon.data.entry.ammo
        is_beam = any(attack.get("delivery") == "beam" for attack in self.weapon.data.entry.attacks.values())

        self.effective.weakpoint_damage = self.modded.weakpoint_damage
        self.effective.fire_rate = self.modded.fire_rate * self.modded.multiplicative_fire_rate
        self.effective.burst_count = self.modded.burst_count
        self.effective.burst_delay = self.modded.burst_delay
        self.effective.charge_time = self.modded.charge_time / self.modded.multiplicative_fire_rate
        self.effective.reload_speed = self.modded.reload_speed + (0 if not is_battery else float("inf") if self.modded.recharge_rate <= 0 else self.modded.magazine_capacity / self.modded.recharge_rate)
        self.effective.recharge_rate = self.modded.recharge_rate
        self.effective.ammo_efficiency = 1 - (1 - self.modded.ammo_efficiency) / (2 if is_beam else 1)
        self.effective.magazine_capacity = self.modded.magazine_capacity
        self.effective.multishot = self.modded.multishot
        self.effective.weakpoint_crit_chance = self.modded.weakpoint_crit_chance * (self.modded.multiplicative_crit_chance + self.modded.multiplicative_weakpoint_crit_chance - 1) + self.modded.flat_crit_chance
        self.effective.internal_bleeding = self.modded.internal_bleeding

    def _compute_average_stats(self) -> None:
        super()._compute_average_stats()
        self._compute_related_attacks()
        is_beam = any(attack.get("delivery") == "beam" for attack in self.weapon.data.entry.attacks.values())
        related_flat = sum(state.damage.total_damage() * state.multishot * state.faction_damage * (1 + state.crit_chance * (state.crit_damage - 1)) for state in self.related.values())
        related_weakpoint = sum(state.damage.total_damage() * state.multishot * state.faction_damage * state.weakpoint_damage * (1 + state.weakpoint_crit_chance * (state.crit_damage - 1)) for state in self.related.values())
        related_dot = sum((sum(multiplier * state.damage.get(damage_type) * state.damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * state.status_chance + sum(multiplier * state.forced_procs.get(damage_type) * state.damage.get(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS)) * (1 + state.crit_chance * (state.crit_damage - 1)) * state.status_damage * state.faction_damage ** 2 * state.multishot for state in self.related.values())
        self.related_dot = related_dot

        self.average.weakpoint_crit_chance = self.effective.weakpoint_crit_chance
        self.average.fire_rate = self._average_fire_rate()
        self.average.procs_per_shot = self.effective.status_chance * self.effective.multishot
        self.average.weakpoint_crit_multiplier = 1 + self.average.weakpoint_crit_chance * (self.effective.crit_damage - 1)
        self.average.beam_dot_multiplier = self.effective.multishot if is_beam else 1
        self.average.flat_dph = self.effective.damage.total_damage() * self.effective.multishot * self.effective.faction_damage * self.average.crit_multiplier + related_flat
        self.average.flat_weakpoint_dph = self.effective.damage.total_damage() * self.effective.multishot * self.effective.weakpoint_damage * self.average.weakpoint_crit_multiplier * self.effective.faction_damage + related_weakpoint
        self.average.flat_dps = self.average.fire_rate * self.average.flat_dph
        self.average.flat_weakpoint_dps = self.average.fire_rate * self.average.flat_weakpoint_dph
        self.average.flat_dotph = self._flat_dotph_for(self.effective.damage, self.base.forced_procs, self.average.crit_chance, self.average.crit_multiplier) + related_dot
        self.average.flat_weakpoint_dotph = self._flat_dotph_for(self.effective.damage, self.base.forced_procs, self.average.weakpoint_crit_chance, self.average.weakpoint_crit_multiplier) + related_dot
        self.average.flat_dotps = self.average.fire_rate * self.average.flat_dotph
        self.average.flat_weakpoint_dotps = self.average.fire_rate * self.average.flat_weakpoint_dotph
        self.average.total_dph = self.average.flat_dph + self.average.flat_dotph
        self.average.total_weakpoint_dph = self.average.flat_weakpoint_dph + self.average.flat_weakpoint_dotph
        self.average.total_dps = self.average.flat_dps + self.average.flat_dotps
        self.average.total_weakpoint_dps = self.average.flat_weakpoint_dps + self.average.flat_weakpoint_dotps

    def _compute_related_attacks(self) -> None:
        self.related_base: dict[str, CalculatedStats] = {}
        self.related: dict[str, CalculatedStats] = {}
        child_names = self.weapon.mode.get("children", [])
        build = self.build.stats.total
        for name in child_names:
            mode = self.weapon.data.entry.attacks.get(name)
            if mode is None:
                continue
            display_name = name.replace("_", " ").title()
            base = self.weapon.mode_stats_type(dict(mode.stats)).with_defaults()
            self.related_base[display_name] = CalculatedStats(base)
            state = CalculatedStats()
            damage = base["damage"].apply(build.damage).combine().sorted()
            co_bonus = self._condition_overload_bonus(build, damage, base["forced_procs"], mode.stats.co_factor)
            base_damage = max(1 + build.base_damage + (co_bonus if mode.stats.co_effect != "multiplies" else 0), 0)
            multiplicative_damage = max(1 + build.multiplicative_base_damage + (co_bonus if mode.stats.co_effect == "multiplies" else 0), 1)
            state.damage = base_damage * damage * multiplicative_damage
            state.forced_procs = base["forced_procs"]
            state.faction_damage = self.effective.faction_damage
            state.crit_chance = max(base["crit_chance"] * (1 + build.crit_chance) * self.modded.multiplicative_crit_chance + self.modded.flat_crit_chance, 0)
            state.crit_damage = max(base["crit_damage"] * (1 + build.crit_damage) + self.modded.flat_crit_damage, 1)
            state.status_chance = max(base["status_chance"] * (1 + build.status_chance), 0)
            state.status_damage = self.effective.status_damage
            state.multishot = max(base["multishot"] * (1 if build.multishot_lock else (1 + build.multishot)), 1)
            state.weakpoint_damage = self.effective.weakpoint_damage
            state.weakpoint_crit_chance = state.crit_chance + max(base["crit_chance"] * build.weakpoint_crit_chance, 0)
            self.related[display_name] = state

    def _average_fire_rate(self) -> float:
        cycle_time = self.effective.magazine_capacity / self.effective.burst_count * (self.effective.charge_time + (self.effective.burst_count - 1) * self.effective.burst_delay) + (self.effective.magazine_capacity / self.effective.burst_count - (1 - self.effective.ammo_efficiency)) / self.effective.fire_rate + (1 - self.effective.ammo_efficiency) * self.effective.reload_speed
        if cycle_time <= 0:
            return float("inf")
        return self.effective.magazine_capacity / cycle_time
