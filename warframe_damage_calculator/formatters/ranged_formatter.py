from __future__ import annotations

from ..calculators import RangedCalculator
from ..states import RangedState
from .weapon_formatter import WeaponFormatter


class RangedFormatter[TRangedState: RangedState](WeaponFormatter[TRangedState]):
    def __init__(self, calculator: RangedCalculator[TRangedState]) -> None:
        super().__init__(calculator)

    def summary(self) -> str:
        return "\n".join([
            f"{'FIRE RATE:':<25} {f'{self.calculator.base.fire_rate:.2f}rps':<7} -> {self.calculator.effective.fire_rate:.2f}rps",
            f"{'RELOAD SPEED:':<25} {f'{self.calculator.base.reload_speed:.2f}s':<7} -> {self.calculator.effective.reload_speed:.2f}s",
            f"{'MAGAZINE CAPACITY:':<25} {f'{self.calculator.base.magazine_capacity:.0f}r':<7} -> {self.calculator.effective.magazine_capacity:.0f}r",
            f"{'MULTISHOT:':<25} {f'{self.calculator.base.multishot:.2f}x':<7} -> {self.calculator.effective.multishot:.2f}x",
            f"{'CRIT CHANCE | WEAKPOINT:':<25} {f'{self.calculator.base.crit_chance:.2%}':<7} -> {self.calculator.effective.crit_chance:.2%} | {self.calculator.effective.weakpoint_crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<25} {f'{self.calculator.base.crit_damage:.2f}x':<7} -> {self.calculator.effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<25} {f'{self.calculator.base.status_chance:.2%}':<7} -> {self.calculator.effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<25} {'1.00x':<7} -> {self.calculator.effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<25} {f'{self.calculator.base.damage.get(dt):.2f}':<7} -> {self.calculator.effective.damage.get(dt):.2f}" for dt, _ in self.calculator.effective.damage),
            f"{'TOTAL DAMAGE | WEAKPOINT:':<25} {f'{self.calculator.base.total_damage * self.calculator.base.multishot:.2f}':<7} -> {self.calculator.effective.total_damage * self.calculator.effective.multishot:.2f} | {self.calculator.effective.total_damage * self.calculator.effective.multishot * self.calculator.effective.weakpoint_damage:.2f}",
            *(f"{f'{dt.upper()}:':<25} {f'{self.calculator.base.explosion_damage.get(dt):.2f}':<7} -> {self.calculator.effective.explosion_damage.get(dt):.2f}" for dt, _ in self.calculator.effective.explosion_damage),
            f"{'TOTAL EXPLOSION DAMAGE:':<25} {f'{self.calculator.base.explosion_total_damage:.2f}':<7} -> {self.calculator.effective.explosion_total_damage:.2f}",
            "----------------------------------------------------------",
            f"{'AVERAGE FIRE RATE:':<25} {self.calculator.average_fire_rate:.2f}rps",
            f"{'EXPECTED PROCS PER SHOT:':<25} {self.calculator.average_procs_per_shot:.2f}",
            f"{'FLAT DPH | WEAKPOINT:':<25} {self.calculator.flat_dph:.2f} | {self.calculator.flat_weakpoint_dph:.2f}",
            f"{'FLAT DOTPH | WEAKPOINT:':<25} {self.calculator.flat_dotph:.2f} | {self.calculator.flat_weakpoint_dotph:.2f}",
            f"{'TOTAL DPH | WEAKPOINT:':<25} {self.calculator.total_dph:.2f} | {self.calculator.total_weakpoint_dph:.2f}",
            f"{'FLAT DPS | WEAKPOINT:':<25} {self.calculator.flat_dps:.2f} | {self.calculator.flat_weakpoint_dps:.2f}",
            f"{'FLAT DOTPS | WEAKPOINT:':<25} {self.calculator.flat_dotps:.2f} | {self.calculator.flat_weakpoint_dotps:.2f}",
            f"{'TOTAL DPS | WEAKPOINT:':<25} {self.calculator.total_dps:.2f} | {self.calculator.total_weakpoint_dps:.2f}",
            "----------------------------------------------------------"
        ])
