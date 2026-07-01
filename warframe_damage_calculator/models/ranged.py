from __future__ import annotations

from ..mechanics.functions import true_round
from ..mechanics.states import RangedState
from .weapon import Weapon


class Ranged(Weapon):
    def __init__(self, base: RangedState | None = None) -> None:
        super().__init__(base)

    def __post_init__(self) -> None:
        self.base.explosion_total_damage = self.base.explosion_damage_dist.total_damage
        super().__post_init__()

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.explosion_damage_dist = self.moded.base_damage * self.base.explosion_damage_dist.apply(self.config.damage_dist).combine()
        self.moded.explosion_total_damage = self.moded.explosion_damage_dist.total_damage
        self.moded.weakpoint_damage = self.base.weakpoint_damage + self.config.weakpoint_damage
        self.moded.multiplicative_fire_rate = 1 + self.config.multiplicative_fire_rate
        self.moded.fire_rate = self.base.fire_rate * (1 + self.config.fire_rate)
        self.moded.charge_time = self.base.charge_time / (1 + self.config.fire_rate)
        self.moded.reload_speed = self.base.reload_speed / (1 + self.config.reload_speed)
        self.moded.magazine_capacity = true_round(self.base.magazine_capacity * (1 + self.config.magazine_capacity))
        self.moded.ammo_efficiency = self.config.ammo_efficiency
        self.moded.multishot = self.base.multishot * (1 + self.config.multishot)
        self.moded.multiplicative_weakpoint_crit_chance = 1 + self.config.multiplicative_weakpoint_crit_chance
        self.moded.weakpoint_crit_chance = self.base.crit_chance * (1 + self.config.crit_chance + self.config.weakpoint_crit_chance)
        self.moded.internal_bleeding = self.config.internal_bleeding * (2 if self.moded.fire_rate * self.moded.multiplicative_fire_rate < 2.5 else 1)

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

    def average_fire_rate(self) -> float:
        if self.effective.magazine_capacity == 1:
            return 1 / self.effective.reload_speed
        return (self.effective.magazine_capacity / (1 - self.effective.ammo_efficiency)) / ( self.effective.magazine_capacity / (1 - self.effective.ammo_efficiency) * (1 / self.effective.fire_rate + self.effective.charge_time) + self.effective.reload_speed)

    def weakpoint_crit_probability_for_tier(self, tier: int) -> float:
        return max(0, 1 - abs(self.effective.weakpoint_crit_chance - tier))

    def average_weakpoint_crit_multiplier(self) -> float:
        return 1 + self.effective.weakpoint_crit_chance * (self.effective.crit_damage - 1)

    def flat_dph(self) -> float:
        return (self.effective.total_damage * self.effective.multishot + self.effective.explosion_total_damage) * self.effective.faction_damage * self.average_crit_multiplier()

    def flat_weakpoint_dph(self) -> float:
        return (self.effective.total_damage * self.effective.multishot * self.effective.weakpoint_damage * self.average_weakpoint_crit_multiplier() + self.effective.explosion_total_damage * self.average_crit_multiplier()) * self.effective.faction_damage

    def flat_dps(self) -> float:
        return self.average_fire_rate() * self.flat_dph()

    def flat_weakpoint_dps(self) -> float:
        return self.average_fire_rate() * self.flat_weakpoint_dph()

    def beam_dot_multiplier(self) -> float:
        return self.effective.multishot if self.base.is_beam else 1

    def flat_dotph(self) -> float:
        direct_damage = self.flat_dotph_for(self.effective.damage_dist, self.base.forced_procs, self.effective.crit_chance, self.average_crit_multiplier())
        explosion_damage = self.flat_dotph_for(self.effective.explosion_damage_dist, self.base.explosion_forced_procs, self.effective.crit_chance, self.average_crit_multiplier(), include_multishot=False)
        return direct_damage + explosion_damage

    def flat_weakpoint_dotph(self) -> float:
        direct_damage = self.flat_dotph_for(self.effective.damage_dist, self.base.forced_procs, self.effective.weakpoint_crit_chance, self.average_weakpoint_crit_multiplier())
        explosion_damage = self.flat_dotph_for(self.effective.explosion_damage_dist, self.base.explosion_forced_procs, self.effective.crit_chance, self.average_crit_multiplier(), include_multishot=False)
        return direct_damage + explosion_damage

    def flat_dotps(self) -> float:
        return self.average_fire_rate() * self.flat_dotph()

    def flat_weakpoint_dotps(self) -> float:
        return self.average_fire_rate() * self.flat_weakpoint_dotph()

    def total_weakpoint_dph(self) -> float:
        return self.flat_weakpoint_dph() + self.flat_weakpoint_dotph()

    def total_weakpoint_dps(self) -> float:
        return self.flat_weakpoint_dps() + self.flat_weakpoint_dotps()

    def summary(self) -> str:
        return "\n".join([
            f"{'FIRE RATE:':<25} {f'{self.base.fire_rate:.2f}rps':<7} -> {self.effective.fire_rate:.2f}rps",
            f"{'RELOAD SPEED:':<25} {f'{self.base.reload_speed:.2f}s':<7} -> {self.effective.reload_speed:.2f}s",
            f"{'MAGAZINE CAPACITY:':<25} {f'{self.base.magazine_capacity:.0f}r':<7} -> {self.effective.magazine_capacity:.0f}r",
            f"{'MULTISHOT:':<25} {f'{self.base.multishot:.2f}x':<7} -> {self.effective.multishot:.2f}x",
            f"{'CRIT CHANCE | WEAKPOINT:':<25} {f'{self.base.crit_chance:.2%}':<7} -> {self.effective.crit_chance:.2%} | {self.effective.weakpoint_crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<25} {f'{self.base.crit_damage:.2f}x':<7} -> {self.effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<25} {f'{self.base.status_chance:.2%}':<7} -> {self.effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<25} {'1.00x':<7} -> {self.effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<25} {f'{self.base.damage_dist.get(dt):.2f}':<7} -> {self.effective.damage_dist.get(dt):.2f}" for dt, _ in self.effective.damage_dist),
            f"{'TOTAL DAMAGE | WEAKPOINT:':<25} {f'{self.base.total_damage * self.base.multishot:.2f}':<7} -> {self.effective.total_damage * self.effective.multishot:.2f} | {self.effective.total_damage * self.effective.multishot * self.effective.weakpoint_damage:.2f}",
            *(f"{f'{dt.upper()}:':<25} {f'{self.base.explosion_damage_dist.get(dt):.2f}':<7} -> {self.effective.explosion_damage_dist.get(dt):.2f}" for dt, _ in self.effective.explosion_damage_dist),
            f"{'TOTAL EXPLOSION DAMAGE:':<25} {f'{self.base.explosion_total_damage:.2f}':<7} -> {self.effective.explosion_total_damage:.2f}",
            "----------------------------------------------------------",
            f"{'AVERAGE FIRE RATE:':<25} {self.average_fire_rate():.2f}rps",
            f"{'EXPECTED PROCS PER SHOT:':<25} {self.effective.status_chance:.2f}",
            f"{'FLAT DPH | WEAKPOINT:':<25} {self.flat_dph():.2f} | {self.flat_weakpoint_dph():.2f}",
            f"{'FLAT DOTPH | WEAKPOINT:':<25} {self.flat_dotph():.2f} | {self.flat_weakpoint_dotph():.2f}",
            f"{'TOTAL DPH | WEAKPOINT:':<25} {self.total_dph():.2f} | {self.total_weakpoint_dph():.2f}",
            f"{'FLAT DPS | WEAKPOINT:':<25} {self.flat_dps():.2f} | {self.flat_weakpoint_dps():.2f}",
            f"{'FLAT DOTPS | WEAKPOINT:':<25} {self.flat_dotps():.2f} | {self.flat_weakpoint_dotps():.2f}",
            f"{'TOTAL DPS | WEAKPOINT:':<25} {self.total_dps():.2f} | {self.total_weakpoint_dps():.2f}",
            "----------------------------------------------------------",
        ])