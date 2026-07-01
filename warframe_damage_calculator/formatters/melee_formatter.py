"""Formatter for melee weapon stats."""

from __future__ import annotations

from .weapon_formatter import WeaponFormatter


class MeleeFormatter(WeaponFormatter):

    def summary(self) -> str:
        return "\n".join([
            f"{'ATTACK SPEED:':<14} {f'{self.weapon.base.attack_speed:.2f}x':<6} -> {self.weapon.effective.attack_speed:.2f}x",
            f"{'CRIT CHANCE:':<14} {f'{self.weapon.base.crit_chance:.2%}':<6} -> {self.weapon.effective.crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<14} {f'{self.weapon.base.crit_damage:.2f}x':<6} -> {self.weapon.effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<14} {f'{self.weapon.base.status_chance:.2%}':<6} -> {self.weapon.effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<14} {'1.00x':<6} -> {self.weapon.effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<14} {f'{self.weapon.base.damage_dist.get(dt):.2f}':<6} -> {self.weapon.effective.damage_dist.get(dt):.2f}" for dt, _ in self.weapon.effective.damage_dist),
            f"{'TOTAL DAMAGE:':<14} {f'{self.weapon.base.total_damage:.2f}':<6} -> {self.weapon.effective.total_damage:.2f}",
            "-------------------------------------",
            f"{'FLAT DPH:':<14} {self.calc.flat_dph():.2f}",
            f"{'FLAT DOTPH:':<14} {self.calc.flat_dotph():.2f}",
            f"{'TOTAL DPH:':<14} {self.calc.total_dph():.2f}",
            f"{'FLAT DPS:':<14} {self.calc.flat_dps():.2f} x BASE HPS",
            f"{'FLAT DOTPS:':<14} {self.calc.flat_dotps():.2f} x BASE HPS",
            f"{'TOTAL DPS:':<14} {self.calc.total_dps():.2f} x BASE HPS",
            "-------------------------------------",
        ])
