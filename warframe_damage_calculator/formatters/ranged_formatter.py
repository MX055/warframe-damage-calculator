from ..calculators.weapon_calculator import WeaponCalculator
from .weapon_formatter import WeaponFormatter


class RangedFormatter(WeaponFormatter):
    def _append_unique_average_rows(self, rows: list[tuple[str, ...]], average) -> None:
        return

    def summary(self) -> str:
        selected = self.weapon.results.main
        base = selected.base
        effective = selected.effective
        average = selected.average
        final = selected.final
        total_base = base.damage.total_damage() * base.multishot
        total_effective = effective.damage.total_damage() * effective.multishot
        hit_multiplier = WeaponCalculator._hit_multiplier(
            average.crit_chance,
            effective.crit_damage,
            effective.get("non_crit_bonus_damage", 0),
            effective.get("non_crit_bonus_chance", 0),
        )
        weakpoint_hit_multiplier = WeaponCalculator._hit_multiplier(
            average.weakpoint_crit_chance,
            effective.crit_damage,
            effective.get("non_crit_bonus_damage", 0),
            effective.get("non_crit_bonus_chance", 0),
        )

        rows: list[tuple[str, ...]] = []
        self._falloff_row(rows, base, effective)
        self._append(rows, "RANGE", self._fmt_meters(base.get("range", 0)), self._fmt_meters(effective.get("range", 0)), self._fmt_meters(effective.get("range", 0)), when=float(effective.get("range", 0) or 0) > 0)
        self._append(rows, "FIRE RATE", self._fmt_rate(base.fire_rate), self._fmt_rate(effective.fire_rate), self._fmt_rate(final.fire_rate))
        self._append(rows, "RELOAD SPEED", self._fmt_seconds(base.reload_speed), self._fmt_seconds(effective.reload_speed), self._fmt_seconds(effective.reload_speed))
        self._append(rows, "RECHARGE RATE", self._fmt_rate(base.get("recharge_rate", 0)), self._fmt_rate(effective.get("recharge_rate", 0)), self._fmt_rate(effective.get("recharge_rate", 0)), when=float(effective.get("recharge_rate", 0) or 0) > 0)
        self._append(rows, "MAGAZINE CAPACITY", self._fmt_rounds(base.magazine_capacity), self._fmt_rounds(effective.magazine_capacity), self._fmt_rounds(effective.magazine_capacity))
        self._append(rows, "AMMO COST", self._fmt_number(base.ammo_cost), self._fmt_number(effective.ammo_cost), self._fmt_number(effective.ammo_cost))
        self._append(rows, "MULTISHOT", self._fmt_multiplier(base.multishot), self._fmt_multiplier(effective.multishot), self._fmt_multiplier(effective.multishot))
        self._append(rows, "BURST COUNT", f"{int(base.get('burst_count', 1))}", f"{int(effective.get('burst_count', 1))}", f"{int(effective.get('burst_count', 1))}", when=int(effective.get("burst_count", 1) or 1) > 1)
        self._append(rows, "BURST DELAY", self._fmt_seconds(base.get("burst_delay", 0)), self._fmt_seconds(effective.get("burst_delay", 0)), self._fmt_seconds(effective.get("burst_delay", 0)), when=float(effective.get("burst_delay", 0) or 0) > 0)
        self._append(rows, "CHARGE TIME", self._fmt_seconds(base.get("charge_time", 0)), self._fmt_seconds(effective.get("charge_time", 0)), self._fmt_seconds(effective.get("charge_time", 0)), when=float(effective.get("charge_time", 0) or 0) > 0)
        self._append(
            rows,
            "CRIT CHANCE",
            self._fmt_percent(base.crit_chance),
            self._with_weakpoint(self._fmt_percent(effective.crit_chance), self._fmt_percent(effective.weakpoint_crit_chance)),
            self._with_weakpoint(self._fmt_percent(average.crit_chance), self._fmt_percent(average.weakpoint_crit_chance)),
        )
        self._append(rows, "CRIT DAMAGE", self._fmt_multiplier(base.crit_damage), self._fmt_multiplier(effective.crit_damage), self._fmt_multiplier(effective.crit_damage))
        self._append(rows, "STATUS CHANCE", self._fmt_percent(base.status_chance), self._fmt_percent(effective.status_chance), self._fmt_percent(effective.status_chance))
        self._append(rows, "WEAKPOINT DAMAGE", self._fmt_multiplier(base.weakpoint_damage), self._fmt_multiplier(effective.weakpoint_damage), self._fmt_multiplier(effective.weakpoint_damage))

        section_breaks: list[int] = []
        damage_at = len(rows)
        self._append_damage_type_rows(rows, base.damage, effective.damage)
        self._append(
            rows,
            "TOTAL DAMAGE",
            self._fmt_number(total_base),
            self._with_weakpoint(self._fmt_number(total_effective), self._fmt_number(total_effective * effective.weakpoint_damage)),
            self._with_weakpoint(self._fmt_number(final.flat_dph), self._fmt_number(final.flat_weakpoint_dph)),
        )
        for child in self.weapon.results.child:
            name = self._attack_label(child.name)
            related_base, related = child.base, child.effective
            self._append_damage_type_rows(rows, related_base.damage, related.damage, prefix=f"{name} ")
            self._append(
                rows,
                f"{name} TOTAL DAMAGE",
                self._fmt_number(related_base.damage.total_damage() * related_base.multishot),
                self._fmt_number(related.damage.total_damage() * related.multishot),
                self._fmt_number(child.average.get("flat_dph", related.damage.total_damage() * related.multishot)),
            )
        if damage_at < len(rows):
            section_breaks.append(damage_at)

        averages_at = len(rows)
        self._append(rows, "HIT MULTIPLIER", "", "", self._with_weakpoint(self._fmt_multiplier(hit_multiplier), self._fmt_multiplier(weakpoint_hit_multiplier)))
        self._append(rows, "EXPECTED PROCS PER SHOT", "", "", self._fmt_number(average.procs_per_shot))
        self._append_unique_average_rows(rows, average)
        section_breaks.append(averages_at)

        dps_at = len(rows)
        self._append(rows, "FLAT DPH", "", "", self._with_weakpoint(self._fmt_number(final.flat_dph), self._fmt_number(final.flat_weakpoint_dph)))
        self._append(rows, "FLAT DOTPH", "", "", self._with_weakpoint(self._fmt_number(final.flat_dotph), self._fmt_number(final.flat_weakpoint_dotph)))
        self._append(rows, "TOTAL DPH", "", "", self._with_weakpoint(self._fmt_number(final.total_dph), self._fmt_number(final.total_weakpoint_dph)))
        self._append(rows, "FLAT DPS", "", "", self._with_weakpoint(self._fmt_number(final.flat_dps), self._fmt_number(final.flat_weakpoint_dps)))
        self._append(rows, "FLAT DOTPS", "", "", self._with_weakpoint(self._fmt_number(final.flat_dotps), self._fmt_number(final.flat_weakpoint_dotps)))
        self._append(rows, "TOTAL DPS", "", "", self._with_weakpoint(self._fmt_number(final.total_dps), self._fmt_number(final.total_weakpoint_dps)))
        section_breaks.append(dps_at)

        title = f"{self.weapon.data.name} - {selected.name.replace('_', ' ').title()}"
        return self._table(("stat", "base", "effective", "final"), rows, title=title, border="=", section_at=tuple(section_breaks))
