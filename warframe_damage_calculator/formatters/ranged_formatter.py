"""Formatter for ranged weapon stats."""

from __future__ import annotations

from .weapon_formatter import WeaponFormatter


class RangedFormatter(WeaponFormatter):

    def summary(self) -> str:
        from ..calculators.ranged_calculator import RangedCalculator

        calc = self.calc
        assert isinstance(calc, RangedCalculator)

        return "\n".join([
            f"{'FIRE RATE:':<25} {f'{self.weapon.base.fire_rate:.2f}rps':<7} -> {self.weapon.effective.fire_rate:.2f}rps",
            f"{'RELOAD SPEED:':<25} {f'{self.weapon.base.reload_speed:.2f}s':<7} -> {self.weapon.effective.reload_speed:.2f}s",
            f"{'MAGAZINE CAPACITY:':<25} {f'{self.weapon.base.magazine_capacity:.0f}r':<7} -> {self.weapon.effective.magazine_capacity:.0f}r",
            f"{'MULTISHOT:':<25} {f'{self.weapon.base.multishot:.2f}x':<7} -> {self.weapon.effective.multishot:.2f}x",
            f"{'CRIT CHANCE | WEAKPOINT:':<25} {f'{self.weapon.base.crit_chance:.2%}':<7} -> {self.weapon.effective.crit_chance:.2%} | {self.weapon.effective.weakpoint_crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<25} {f'{self.weapon.base.crit_damage:.2f}x':<7} -> {self.weapon.effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<25} {f'{self.weapon.base.status_chance:.2%}':<7} -> {self.weapon.effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<25} {'1.00x':<7} -> {self.weapon.effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<25} {f'{self.weapon.base.damage_dist.get(dt):.2f}':<7} -> {self.weapon.effective.damage_dist.get(dt):.2f}" for dt, _ in self.weapon.effective.damage_dist),
            f"{'TOTAL DAMAGE | WEAKPOINT:':<25} {f'{self.weapon.base.total_damage * self.weapon.base.multishot:.2f}':<7} -> {self.weapon.effective.total_damage * self.weapon.effective.multishot:.2f} | {self.weapon.effective.total_damage * self.weapon.effective.multishot * self.weapon.effective.weakpoint_damage:.2f}",
            *(f"{f'{dt.upper()}:':<25} {f'{self.weapon.base.explosion_damage_dist.get(dt):.2f}':<7} -> {self.weapon.effective.explosion_damage_dist.get(dt):.2f}" for dt, _ in self.weapon.effective.explosion_damage_dist),
            f"{'TOTAL EXPLOSION DAMAGE:':<25} {f'{self.weapon.base.explosion_total_damage:.2f}':<7} -> {self.weapon.effective.explosion_total_damage:.2f}",
            "----------------------------------------------------------",
            f"{'AVERAGE FIRE RATE:':<25} {calc.average_fire_rate():.2f}rps",
            f"{'EXPECTED PROCS PER SHOT:':<25} {calc.average_procs_per_shot():.2f}",
            f"{'FLAT DPH | WEAKPOINT:':<25} {calc.flat_dph():.2f} | {calc.flat_weakpoint_dph():.2f}",
            f"{'FLAT DOTPH | WEAKPOINT:':<25} {calc.flat_dotph():.2f} | {calc.flat_weakpoint_dotph():.2f}",
            f"{'TOTAL DPH | WEAKPOINT:':<25} {calc.total_dph():.2f} | {calc.total_weakpoint_dph():.2f}",
            f"{'FLAT DPS | WEAKPOINT:':<25} {calc.flat_dps():.2f} | {calc.flat_weakpoint_dps():.2f}",
            f"{'FLAT DOTPS | WEAKPOINT:':<25} {calc.flat_dotps():.2f} | {calc.flat_weakpoint_dotps():.2f}",
            f"{'TOTAL DPS | WEAKPOINT:':<25} {calc.total_dps():.2f} | {calc.total_weakpoint_dps():.2f}",
            "----------------------------------------------------------",
        ])
