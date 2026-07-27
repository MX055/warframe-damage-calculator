from math import isclose

from ..engine import formulas
from .weapon_formatter import WeaponFormatter


class RangedFormatter(WeaponFormatter):
    def _append_unique_average_rows(self, rows: list[tuple[str, ...]], average) -> None:
        return

    def _weakpoint_crit_flags(self, selected, effective, average) -> tuple[bool, bool, float, float]:
        hit_multiplier = formulas.hit_multiplier(average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        weakpoint_hit_multiplier = formulas.hit_multiplier(average.weakpoint_crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        weakpoint_crit_modifier = any(float(bucket.get("weakpoint_crit_chance", 0) or 0) != 0 for source in (selected.build, selected.evolutions) for bucket in (source.proportional, source.base, source.flat)) or not isclose(formulas.fold_multiplicative_families(selected.build, selected.evolutions, stat="weakpoint_crit_chance"), 1)
        show_weakpoint_crit = weakpoint_crit_modifier and not isclose(float(effective.crit_chance), float(effective.weakpoint_crit_chance))
        show_weakpoint_hit = weakpoint_crit_modifier and not isclose(hit_multiplier, weakpoint_hit_multiplier)
        return show_weakpoint_crit, show_weakpoint_hit, hit_multiplier, weakpoint_hit_multiplier

    def _append_related_attack_rows(self, rows: list[tuple[str, ...]]) -> None:
        for child in self.weapon.results.child:
            name = self._attack_label(child.name)
            related_base, related = child.base, child.effective
            self._append_damage_type_rows(rows, related_base.damage, related.damage, prefix=f"{name} ")
            self._append(rows, f"{name} TOTAL DAMAGE", self._fmt_number(related_base.damage.total_damage() * related_base.multishot), self._fmt_number(related.damage.total_damage() * related.multishot), self._fmt_number(child.average.get("flat_dph", related.damage.total_damage() * related.multishot)))

    def summary(self) -> str:
        selected = self.weapon.results.main
        base = selected.base
        effective = selected.effective
        average = selected.average
        final = selected.final
        total_base = base.damage.total_damage() * base.multishot
        total_effective = effective.damage.total_damage() * effective.multishot
        show_weakpoint_crit, show_weakpoint_hit, hit_multiplier, weakpoint_hit_multiplier = self._weakpoint_crit_flags(selected, effective, average)

        rows: list[tuple[str, ...]] = []
        self._falloff_row(rows, base, effective)
        self._append(rows, "RANGE", self._fmt_meters(base.get("range", 0)), self._fmt_meters(effective.get("range", 0)), self._fmt_meters(effective.get("range", 0)), when=float(effective.get("range", 0) or 0) > 0)
        self._append(rows, "FIRE RATE", self._fmt_rate(base.fire_rate), self._fmt_rate(effective.fire_rate), self._fmt_rate(final.fire_rate))
        self._append(rows, "RELOAD SPEED", self._fmt_seconds(base.reload_speed), self._fmt_seconds(effective.reload_speed), self._fmt_seconds(effective.reload_speed))
        self._append(rows, "RECHARGE RATE", self._fmt_rate(base.get("recharge_rate", 0)), self._fmt_rate(effective.get("recharge_rate", 0)), self._fmt_rate(effective.get("recharge_rate", 0)), when=float(effective.get("recharge_rate", 0) or 0) > 0)
        self._append(rows, "MAGAZINE CAPACITY", self._fmt_rounds(base.magazine_capacity), self._fmt_rounds(effective.magazine_capacity), self._fmt_rounds(effective.magazine_capacity))
        self._append(rows, "AMMO MAXIMUM", self._fmt_rounds(base.get("ammo_maximum", 0)), self._fmt_rounds(effective.get("ammo_maximum", 0)), self._fmt_rounds(effective.get("ammo_maximum", 0)), when=float(effective.get("ammo_maximum", 0) or 0) > 0)
        self._append(rows, "AMMO COST", self._fmt_number(base.ammo_cost), self._fmt_number(effective.ammo_cost), self._fmt_number(effective.ammo_cost))
        self._append(rows, "MULTISHOT", self._fmt_multiplier(base.multishot), self._fmt_multiplier(effective.multishot), self._fmt_multiplier(effective.multishot))
        self._append(rows, "PUNCH THROUGH", self._fmt_meters(base.get("punch_through", 0)), self._fmt_meters(effective.get("punch_through", 0)), self._fmt_meters(effective.get("punch_through", 0)), when=float(effective.get("punch_through", 0) or 0) > 0)
        self._append(rows, "ACCURACY", self._fmt_number(base.get("accuracy", 0)), self._fmt_number(effective.get("accuracy", 0)), self._fmt_number(effective.get("accuracy", 0)), when=float(effective.get("accuracy", 0) or 0) != 0)
        self._append(rows, "RECOIL", self._fmt_percent(base.get("recoil", 0)), self._fmt_percent(effective.get("recoil", 0)), self._fmt_percent(effective.get("recoil", 0)), when=float(effective.get("recoil", 0) or 0) != 0)
        self._append(rows, "ZOOM", self._fmt_percent(base.get("zoom", 0)), self._fmt_percent(effective.get("zoom", 0)), self._fmt_percent(effective.get("zoom", 0)), when=float(effective.get("zoom", 0) or 0) != 0)
        self._append(rows, "NOISE LEVEL", str(base.get("noise_level") or ""), str(effective.get("noise_level") or ""), str(effective.get("noise_level") or ""), when=bool(effective.get("noise_level")))
        self._append(rows, "BURST COUNT", f"{int(base.get('burst_count', 1))}", f"{int(effective.get('burst_count', 1))}", f"{int(effective.get('burst_count', 1))}", when=int(effective.get("burst_count", 1) or 1) > 1)
        self._append(rows, "BURST DELAY", self._fmt_seconds(base.get("burst_delay", 0)), self._fmt_seconds(effective.get("burst_delay", 0)), self._fmt_seconds(effective.get("burst_delay", 0)), when=float(effective.get("burst_delay", 0) or 0) > 0)
        self._append(rows, "CHARGE TIME", self._fmt_seconds(base.get("charge_time", 0)), self._fmt_seconds(effective.get("charge_time", 0)), self._fmt_seconds(effective.get("charge_time", 0)), when=float(effective.get("charge_time", 0) or 0) > 0)
        self._append(rows, "CRIT CHANCE", self._fmt_percent(base.crit_chance), self._with_weakpoint(self._fmt_percent(effective.crit_chance), self._fmt_percent(effective.weakpoint_crit_chance) if show_weakpoint_crit else None), self._with_weakpoint(self._fmt_percent(average.crit_chance), self._fmt_percent(average.weakpoint_crit_chance) if show_weakpoint_crit else None))
        self._append(rows, "CRIT DAMAGE", self._fmt_multiplier(base.crit_damage), self._fmt_multiplier(effective.crit_damage), self._fmt_multiplier(effective.crit_damage))
        self._append(rows, "STATUS CHANCE", self._fmt_percent(base.status_chance), self._fmt_percent(effective.status_chance), self._fmt_percent(effective.status_chance))
        self._append(rows, "WEAKPOINT DAMAGE", self._fmt_multiplier(base.weakpoint_damage), self._fmt_multiplier(effective.weakpoint_damage), self._fmt_multiplier(effective.weakpoint_damage))

        section_breaks: list[int] = []
        damage_at = len(rows)
        self._append_damage_type_rows(rows, base.damage, effective.damage)
        self._append(rows, "TOTAL DAMAGE", self._fmt_number(total_base), self._with_weakpoint(self._fmt_number(total_effective), self._fmt_number(total_effective * effective.weakpoint_damage)), self._fmt_zone_metric(final.flat_dph, final.flat_weakpoint_dph, final.flat_resistant_dph))
        self._append_related_attack_rows(rows)
        if damage_at < len(rows):
            section_breaks.append(damage_at)

        averages_at = len(rows)
        self._append(rows, "HIT MULTIPLIER", "", "", self._with_weakpoint(self._fmt_multiplier(hit_multiplier), self._fmt_multiplier(weakpoint_hit_multiplier) if show_weakpoint_hit else None))
        self._append(rows, "EXPECTED PROCS PER SHOT", "", "", self._fmt_number(average.procs_per_shot))
        self._append_unique_average_rows(rows, average)
        section_breaks.append(averages_at)

        section_breaks.append(self._append_zone_metrics_section(rows, final))
        return self._table(("stat", "base", "effective", "final"), rows, title=self._summary_title(selected), border="=", section_at=tuple(section_breaks))
