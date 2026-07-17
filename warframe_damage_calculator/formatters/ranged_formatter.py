from .weapon_formatter import WeaponFormatter


class RangedFormatter(WeaponFormatter):
    def summary(self) -> str:
        base = self.calculator.base
        effective = self.calculator.effective
        return "\n".join([
            f"{'FIRE RATE:':<25} {f'{base.fire_rate:.2f}rps':<7} -> {effective.fire_rate:.2f}rps",
            f"{'RELOAD SPEED:':<25} {f'{base.reload_speed:.2f}s':<7} -> {effective.reload_speed:.2f}s",
            f"{'MAGAZINE CAPACITY:':<25} {f'{base.magazine_capacity:.0f}r':<7} -> {effective.magazine_capacity:.0f}r",
            f"{'MULTISHOT:':<25} {f'{base.multishot:.2f}x':<7} -> {effective.multishot:.2f}x",
            f"{'CRIT CHANCE | WEAKPOINT:':<25} {f'{base.crit_chance:.2%}':<7} -> {effective.crit_chance:.2%} | {effective.weakpoint_crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<25} {f'{base.crit_damage:.2f}x':<7} -> {effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<25} {f'{base.status_chance:.2%}':<7} -> {effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<25} {'1.00x':<7} -> {effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<25} {f'{base.damage.get(dt, 0):.2f}':<7} -> {effective.damage.get(dt):.2f}" for dt in effective.damage),
            f"{'TOTAL DAMAGE | WEAKPOINT:':<25} {f'{base.total_damage * base.multishot:.2f}':<7} -> {effective.total_damage * effective.multishot:.2f} | {effective.total_damage * effective.multishot * effective.weakpoint_damage:.2f}",
            *(f"{f'{dt.upper()}:':<25} {f'{base.explosion_damage.get(dt, 0):.2f}':<7} -> {effective.explosion_damage.get(dt):.2f}" for dt in effective.explosion_damage),
            f"{'TOTAL EXPLOSION DAMAGE:':<25} {f'{base.explosion_total_damage:.2f}':<7} -> {effective.explosion_total_damage:.2f}",
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
