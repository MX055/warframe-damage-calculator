from __future__ import annotations

from ..calculators import MeleeCalculator
from ..states import MeleeState
from .weapon_formatter import WeaponFormatter


class MeleeFormatter(WeaponFormatter[MeleeState]):
    def __init__(self, calculator: MeleeCalculator) -> None:
        super().__init__(calculator)

    def summary(self) -> str:
        return "\n".join([
            f"{'ATTACK SPEED:':<14} {f'{self.calculator.base.attack_speed:.2f}x':<6} -> {self.calculator.effective.attack_speed:.2f}x",
            f"{'CRIT CHANCE:':<14} {f'{self.calculator.base.crit_chance:.2%}':<6} -> {self.calculator.effective.crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<14} {f'{self.calculator.base.crit_damage:.2f}x':<6} -> {self.calculator.effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<14} {f'{self.calculator.base.status_chance:.2%}':<6} -> {self.calculator.effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<14} {'1.00x':<6} -> {self.calculator.effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<14} {f'{self.calculator.base.damage_dist.get(dt):.2f}':<6} -> {self.calculator.effective.damage_dist.get(dt):.2f}" for dt, _ in self.calculator.effective.damage_dist),
            f"{'TOTAL DAMAGE:':<14} {f'{self.calculator.base.total_damage:.2f}':<6} -> {self.calculator.effective.total_damage:.2f}",
            "-------------------------------------",
            f"{'FLAT DPH:':<14} {self.calculator.flat_dph:.2f}",
            f"{'FLAT DOTPH:':<14} {self.calculator.flat_dotph:.2f}",
            f"{'TOTAL DPH:':<14} {self.calculator.total_dph:.2f}",
            f"{'FLAT DPS:':<14} {self.calculator.flat_dps:.2f} x BASE HPS",
            f"{'FLAT DOTPS:':<14} {self.calculator.flat_dotps:.2f} x BASE HPS",
            f"{'TOTAL DPS:':<14} {self.calculator.total_dps:.2f} x BASE HPS",
            "-------------------------------------",
        ])
