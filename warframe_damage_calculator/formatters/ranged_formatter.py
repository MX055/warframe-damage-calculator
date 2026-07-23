from .weapon_formatter import WeaponFormatter


class RangedFormatter(WeaponFormatter):
    def summary(self) -> str:
        attack_name = self.weapon.stats._attack_name()
        selected = self.weapon.stats.attacks[attack_name]
        base = selected.base
        effective = selected.effective
        average = self.weapon.stats.combined
        related_rows = []
        for child_name in selected.children:
            if child_name not in self.weapon.stats.attacks:
                continue
            child = self.weapon.stats.attacks[child_name]
            name = child.name.replace("_", " ").title()
            related_base, related = child.base, child.effective
            damage_types = dict.fromkeys((*related_base.damage.data, *related.damage.data))
            related_rows.extend((f"{name} {damage_type.upper()}:", related_base.damage.get(damage_type), related.damage.get(damage_type)) for damage_type in damage_types)
            related_rows.append((f"{name} TOTAL DAMAGE:", related_base.damage.total_damage() * related_base.multishot, related.damage.total_damage() * related.multishot))

        label_width = max((25, *(len(label) for label, _, _ in related_rows)))
        divider = "-" * (label_width + 33)
        return "\n".join([
            f"{self.weapon.data.name} - {selected.name.replace('_', ' ').title()}",
            divider,
            f"{'FIRE RATE:':<{label_width}} {f'{base.fire_rate:.2f}rps':<7} -> {effective.fire_rate:.2f}rps",
            f"{'RELOAD SPEED:':<{label_width}} {f'{base.reload_speed:.2f}s':<7} -> {effective.reload_speed:.2f}s",
            f"{'MAGAZINE CAPACITY:':<{label_width}} {f'{base.magazine_capacity:.0f}r':<7} -> {effective.magazine_capacity:.0f}r",
            f"{'MULTISHOT:':<{label_width}} {f'{base.multishot:.2f}x':<7} -> {effective.multishot:.2f}x",
            f"{'CRIT CHANCE | WEAKPOINT:':<{label_width}} {f'{base.crit_chance:.2%}':<7} -> {effective.crit_chance:.2%} | {effective.weakpoint_crit_chance:.2%}",
            f"{'CRIT DAMAGE:':<{label_width}} {f'{base.crit_damage:.2f}x':<7} -> {effective.crit_damage:.2f}x",
            f"{'STATUS CHANCE:':<{label_width}} {f'{base.status_chance:.2%}':<7} -> {effective.status_chance:.2%}",
            f"{'STATUS DAMAGE:':<{label_width}} {'1.00x':<7} -> {effective.status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<{label_width}} {f'{base.damage.get(dt, 0):.2f}':<7} -> {effective.damage.get(dt):.2f}" for dt in effective.damage.data),
            f"{'TOTAL DAMAGE | WEAKPOINT:':<{label_width}} {f'{base.damage.total_damage() * base.multishot:.2f}':<7} -> {effective.damage.total_damage() * effective.multishot:.2f} | {effective.damage.total_damage() * effective.multishot * effective.weakpoint_damage:.2f}",
            *(f"{label:<{label_width}} {f'{base_damage:.2f}':<7} -> {effective_damage:.2f}" for label, base_damage, effective_damage in related_rows),
            divider,
            f"{'AVERAGE FIRE RATE:':<{label_width}} {average.fire_rate:.2f}rps",
            f"{'EXPECTED PROCS PER SHOT:':<{label_width}} {selected.average.procs_per_shot:.2f}",
            f"{'FLAT DPH | WEAKPOINT:':<{label_width}} {average.flat_dph:.2f} | {average.flat_weakpoint_dph:.2f}",
            f"{'FLAT DOTPH | WEAKPOINT:':<{label_width}} {average.flat_dotph:.2f} | {average.flat_weakpoint_dotph:.2f}",
            f"{'TOTAL DPH | WEAKPOINT:':<{label_width}} {average.total_dph:.2f} | {average.total_weakpoint_dph:.2f}",
            f"{'FLAT DPS | WEAKPOINT:':<{label_width}} {average.flat_dps:.2f} | {average.flat_weakpoint_dps:.2f}",
            f"{'FLAT DOTPS | WEAKPOINT:':<{label_width}} {average.flat_dotps:.2f} | {average.flat_weakpoint_dotps:.2f}",
            f"{'TOTAL DPS | WEAKPOINT:':<{label_width}} {average.total_dps:.2f} | {average.total_weakpoint_dps:.2f}",
            divider
        ])
