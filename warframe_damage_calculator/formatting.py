from __future__ import annotations

from math import isclose
from typing import Any

from .domain.damage import Dist
from .engine.formulas import hit_multiplier


HEAVY_ATTACK_CATEGORIES = frozenset({"heavy", "heavy_slam"})
SLAM_ATTACK_CATEGORIES = frozenset({"slam", "heavy_slam"})
SLIDE_ATTACK_CATEGORIES = frozenset({"slide"})


class WeaponFormatter:
    __slots__ = ("weapon",)

    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon

    @staticmethod
    def _with_weakpoint(value: str | None, weakpoint: str | None = None) -> str:
        if value is None: return weakpoint or ""
        return value if weakpoint is None else f"{value} | {weakpoint}"

    def _with_hit_zones(self, normal: str | None, weakpoint: str | None, resistant: str | None) -> str:
        if self.weapon.target is None: return self._with_weakpoint(normal, weakpoint)
        return " | ".join(value for value in (normal, weakpoint, resistant) if value is not None)

    @staticmethod
    def _fmt_number(value: float | None) -> str | None:
        return None if value is None else f"{float(value):.2f}"

    @staticmethod
    def _fmt_percent(value: float | None) -> str | None:
        return None if value is None else f"{float(value):.2%}"

    @staticmethod
    def _fmt_bonus_percent(value: float | None) -> str | None:
        return None if value is None else f"+{float(value):.2%}"

    @staticmethod
    def _fmt_multiplier(value: float | None) -> str | None:
        return None if value is None else f"{float(value):.2f}x"

    @staticmethod
    def _fmt_rate(value: float | None) -> str | None:
        return None if value is None else f"{float(value):.2f}rps"

    @staticmethod
    def _fmt_seconds(value: float | None) -> str | None:
        return None if value is None else f"{float(value):.2f}s"

    @staticmethod
    def _fmt_rounds(value: float | None) -> str | None:
        return None if value is None else f"{float(value):.0f}r"

    @staticmethod
    def _fmt_meters(value: float | None) -> str | None:
        return None if value is None else f"{float(value):g}m"

    @staticmethod
    def _fmt_damage_mass(value: float | None, aoe: bool) -> str:
        if value is None: return "-"
        return f"{float(value):.2f}{'m³' if aoe else 'm'}"

    def _hit_zone_label(self) -> str:
        if self.weapon.target is None: return "normal | weakpoint"
        zones = ("normal", "weakpoint", "resistant")
        present = [zone for zone in zones if any(part.type == zone for part in self.weapon.target.bodyparts.values())]
        return " | ".join(present)

    def _summary_title(self, selected: Any) -> str:
        title = f"{self.weapon.name} - {selected.name.replace('_', ' ').title()}"
        if self.weapon.target is not None: title += f" vs {self.weapon.target.name} (bodypart: {self._hit_zone_label()})"
        return title

    def _fmt_zone_metric(self, normal: float | None, weakpoint: float | None, resistant: float | None) -> str:
        return self._with_hit_zones(self._fmt_number(normal), self._fmt_number(weakpoint), self._fmt_number(resistant))

    def _append_zone_metrics_section(self, rows: list[tuple[str, ...]], final: Any) -> int:
        section_at = len(rows)
        self._append(rows, "FLAT DPH", "", "", self._fmt_zone_metric(final.flat_dph, final.flat_weakpoint_dph, final.flat_resistant_dph))
        self._append(rows, "FLAT DOTPH", "", "", self._fmt_zone_metric(final.flat_dotph, final.flat_weakpoint_dotph, final.flat_resistant_dotph))
        self._append(rows, "TOTAL DPH", "", "", self._fmt_zone_metric(final.total_dph, final.total_weakpoint_dph, final.total_resistant_dph))
        self._append(rows, "FLAT DPS", "", "", self._fmt_zone_metric(final.flat_dps, final.flat_weakpoint_dps, final.flat_resistant_dps))
        self._append(rows, "FLAT DOTPS", "", "", self._fmt_zone_metric(final.flat_dotps, final.flat_weakpoint_dotps, final.flat_resistant_dotps))
        self._append(rows, "TOTAL DPS", "", "", self._fmt_zone_metric(final.total_dps, final.total_weakpoint_dps, final.total_resistant_dps))
        return section_at

    def _append_damage_type_rows(self, rows: list[tuple[str, ...]], base_damage: Dist, effective_damage: Dist, *, prefix: str = "") -> None:
        for damage_type in dict.fromkeys((*base_damage, *effective_damage)):
            label = f"{prefix}{damage_type.upper()}".strip()
            self._append(rows, label, self._fmt_number(base_damage.get(damage_type, 0)), self._fmt_number(effective_damage.get(damage_type, 0)), self._fmt_number(effective_damage.get(damage_type, 0)))

    @staticmethod
    def _append(rows: list[tuple[str, ...]], name: str, base: str | None = "", effective: str | None = "", final: str | None = "", *, when: bool = True) -> None:
        if when: rows.append((name, base or "", effective or "", final or ""))

    @staticmethod
    def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]], *, title: str | None = None, section_at: int | tuple[int, ...] | None = None, border: str | None = None) -> str:
        widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
        breaks = set() if section_at is None else {section_at} if isinstance(section_at, int) else set(section_at)

        def format_row(cells: tuple[str, ...]) -> str:
            return " | ".join(f"{cell:<{widths[index]}}" for index, cell in enumerate(cells))

        header = format_row(headers)
        rule = "-" * len(header)
        lines: list[str] = []
        if title: lines.append(title)
        if border: lines.append(border * len(header))
        lines.extend((header, rule))
        for index, row in enumerate(rows):
            if index in breaks: lines.append(rule)
            lines.append(format_row(row))
        if border: lines.append(border * len(header))
        return "\n".join(lines)

    def _falloff_row(self, rows: list[tuple[str, ...]], selected: Any) -> None:
        falloff = selected.attack.stats.falloff
        if "start_range" not in falloff: return

        def format_falloff(start: float, end: float, multiplier: float) -> str:
            return f"{float(start):g}m -> {float(end):g}m @ {float(multiplier):.2%}"

        final_multiplier = falloff.get("final_multiplier")
        base_text = format_falloff(falloff["start_range"], falloff["end_range"], 1 if final_multiplier is None else final_multiplier)
        effective = selected.effective
        effective_text = format_falloff(effective.start_range, effective.end_range, effective.final_multiplier)
        self._append(rows, "FALLOFF", base_text, effective_text, effective_text)

    def _append_falloff_multiplier(self, rows: list[tuple[str, ...]], selected: Any) -> None:
        self._append(rows, "AVERAGE FALLOFF MULTIPLIER", "", "", self._fmt_multiplier(selected.average.falloff_multiplier), when=bool(selected.attack.stats.falloff))

    def _append_damage_mass(self, rows: list[tuple[str, ...]], selected: Any) -> None:
        is_aoe = selected.attack.aoe or selected.attack.category in SLAM_ATTACK_CATEGORIES
        damage_mass = selected.density.damage_mass
        self._append(rows, "DAMAGE MASS", "", "", self._fmt_damage_mass(damage_mass, is_aoe), when=damage_mass is not None and damage_mass > 0)

    @staticmethod
    def _resolved_proportional(selected: Any, stat: str) -> float:
        return float(selected.build.proportional.get(stat, 0)) + float(selected.evolutions.proportional.get(stat, 0))

    def _weakpoint_damage(self, selected: Any) -> tuple[float, float]:
        base = 3.0
        return base, base * (1 + float(selected.effective.weakpoint_damage_bonus))

    def upgrades(self) -> str:
        shapley = self.weapon.results.shapley_contributions()
        if not shapley: return ""
        removal = self.weapon.results.removal_contributions()
        rows = [(name, f"{share:.2%}", f"{removal[name]:.2f}") for name, share in shapley.items()]
        title = f"{self.weapon.name} - {self.weapon.results.main.name.replace('_', ' ').title()}"
        if self.weapon.target is not None: title += f" vs {self.weapon.target.name}"
        return self._table(("upgrade", "shapley", "removal"), rows, title=title, border="=")

    def summary(self) -> str:
        return self._melee_summary() if self.weapon.type == "melee" else self._ranged_summary()

    def _weakpoint_crit_values(self, selected: Any) -> tuple[bool, bool, float, float]:
        effective, average = selected.effective, selected.average
        body_hit = hit_multiplier(average.crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        weakpoint_hit = hit_multiplier(average.weakpoint_crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        show_weakpoint_crit = not isclose(float(effective.crit_chance), float(effective.weakpoint_crit_chance))
        show_weakpoint_hit = show_weakpoint_crit and not isclose(body_hit, weakpoint_hit)
        return show_weakpoint_crit, show_weakpoint_hit, body_hit, weakpoint_hit

    def _append_related_attack_rows(self, rows: list[tuple[str, ...]]) -> None:
        for child in self.weapon.results.child:
            label = child.name.replace("_", " ").upper()
            self._append_damage_type_rows(rows, child.base.damage, child.effective.damage, prefix=f"{label} ")
            base_total = child.base.damage.total * float(child.base.multishot)
            effective_total = child.effective.damage.total * float(child.effective.multishot)
            self._append(rows, f"{label} TOTAL DAMAGE", self._fmt_number(base_total), self._fmt_number(effective_total), self._fmt_number(child.average.flat_dph))

    def _ranged_summary(self) -> str:
        selected = self.weapon.results.main
        attack, base, effective, average, final = selected.attack, selected.base, selected.effective, selected.average, selected.final
        total_base = base.damage.total * float(base.multishot)
        total_effective = effective.damage.total * float(effective.multishot)
        weakpoint_base, weakpoint_effective = self._weakpoint_damage(selected)
        show_weakpoint_crit, show_weakpoint_hit, body_hit, weakpoint_hit = self._weakpoint_crit_values(selected)
        incarnon = attack.form == "incarnon" and self.weapon.incarnon_charges is not None
        magazine_base = float(self.weapon.incarnon_charges) if incarnon else float(self.weapon.magazine_size)

        rows: list[tuple[str, ...]] = []
        self._falloff_row(rows, selected)
        self._append(rows, "RANGE", self._fmt_meters(attack.stats.range), self._fmt_meters(effective.range), self._fmt_meters(effective.range), when=float(effective.range) > 0)
        self._append(rows, "FIRE RATE", self._fmt_rate(base.fire_rate), self._fmt_rate(effective.instantaneous_fire_rate), self._fmt_rate(final.sustained_fire_rate))
        self._append(rows, "RELOAD TIME", self._fmt_seconds(self.weapon.reload_time), self._fmt_seconds(effective.reload_time), self._fmt_seconds(effective.reload_time))
        self._append(rows, "RECHARGE RATE", self._fmt_rate(self.weapon.recharge_rate), self._fmt_rate(self.weapon.recharge_rate), self._fmt_rate(self.weapon.recharge_rate), when=self.weapon.recharge_rate is not None and self.weapon.recharge_rate > 0)
        self._append(rows, "MAGAZINE CAPACITY", self._fmt_rounds(magazine_base), self._fmt_rounds(effective.magazine_capacity), self._fmt_rounds(effective.magazine_capacity))
        self._append(rows, "AMMO MAXIMUM", self._fmt_rounds(getattr(attack.stats, "ammo_maximum", 0)), self._fmt_rounds(effective.ammo_maximum), self._fmt_rounds(effective.ammo_maximum), when=float(effective.ammo_maximum) > 0)
        self._append(rows, "AMMO COST", self._fmt_number(base.get("ammo_cost", attack.stats.ammo_cost)), self._fmt_number(effective.ammo_cost), self._fmt_number(effective.ammo_cost))
        self._append(rows, "MULTISHOT", self._fmt_multiplier(base.multishot), self._fmt_multiplier(effective.multishot), self._fmt_multiplier(effective.multishot))
        self._append(rows, "PUNCH THROUGH", self._fmt_meters(float(attack.stats.punch_through)), self._fmt_meters(effective.punch_through), self._fmt_meters(effective.punch_through), when=float(effective.punch_through) > 0)
        self._append(rows, "ACCURACY", self._fmt_number(attack.stats.accuracy), self._fmt_number(effective.accuracy), self._fmt_number(effective.accuracy), when=float(effective.accuracy) != 0)
        self._append(rows, "RECOIL", self._fmt_percent(attack.stats.recoil), self._fmt_percent(effective.recoil), self._fmt_percent(effective.recoil), when=float(effective.recoil) != 0)
        self._append(rows, "ZOOM", self._fmt_percent(attack.stats.zoom), self._fmt_percent(effective.zoom), self._fmt_percent(effective.zoom), when=float(effective.zoom) != 0)
        self._append(rows, "NOISE LEVEL", attack.stats.noise_level, str(effective.noise_level), str(effective.noise_level), when=bool(effective.noise_level))
        self._append(rows, "BURST COUNT", f"{int(attack.stats.burst_count)}", f"{int(effective.burst_count)}", f"{int(effective.burst_count)}", when=int(effective.burst_count) > 1)
        self._append(rows, "BURST DELAY", self._fmt_seconds(attack.stats.burst_delay), self._fmt_seconds(effective.burst_delay), self._fmt_seconds(effective.burst_delay), when=float(effective.burst_delay) > 0)
        self._append(rows, "CHARGE TIME", self._fmt_seconds(attack.stats.charge_time), self._fmt_seconds(effective.charge_time), self._fmt_seconds(effective.charge_time), when=float(effective.charge_time) > 0)
        self._append(rows, "CRIT CHANCE", self._fmt_percent(base.crit_chance), self._with_weakpoint(self._fmt_percent(effective.crit_chance), self._fmt_percent(effective.weakpoint_crit_chance) if show_weakpoint_crit else None), self._with_weakpoint(self._fmt_percent(average.crit_chance), self._fmt_percent(average.weakpoint_crit_chance) if show_weakpoint_crit else None))
        self._append(rows, "CRIT DAMAGE", self._fmt_multiplier(base.crit_damage), self._fmt_multiplier(effective.crit_damage), self._fmt_multiplier(effective.crit_damage))
        self._append(rows, "STATUS CHANCE", self._fmt_percent(base.status_chance), self._fmt_percent(effective.status_chance), self._fmt_percent(effective.status_chance))
        self._append(rows, "WEAKPOINT DAMAGE", self._fmt_multiplier(weakpoint_base), self._fmt_multiplier(weakpoint_effective), self._fmt_multiplier(weakpoint_effective))

        section_breaks: list[int] = []
        damage_at = len(rows)
        self._append_damage_type_rows(rows, base.damage, effective.damage)
        self._append(rows, "TOTAL DAMAGE", self._fmt_number(total_base), self._with_weakpoint(self._fmt_number(total_effective), self._fmt_number(total_effective * weakpoint_effective)), self._fmt_zone_metric(final.flat_dph, final.flat_weakpoint_dph, final.flat_resistant_dph))
        self._append_related_attack_rows(rows)
        if damage_at < len(rows): section_breaks.append(damage_at)

        averages_at = len(rows)
        self._append(rows, "HIT MULTIPLIER", "", "", self._with_weakpoint(self._fmt_multiplier(body_hit), self._fmt_multiplier(weakpoint_hit) if show_weakpoint_hit else None))
        self._append_falloff_multiplier(rows, selected)
        self._append_damage_mass(rows, selected)
        self._append(rows, "EXPECTED PROCS PER SHOT", "", "", self._fmt_number(average.procs_per_shot))
        if self.weapon.type == "primary":
            self._append(rows, "FIRST SHOT DAMAGE MULTIPLIER", "", "", self._fmt_multiplier(average.first_shot_damage_multiplier), when=float(average.first_shot_damage_multiplier) != 1)
        elif self.weapon.type == "secondary":
            bonus = self._with_weakpoint(self._fmt_bonus_percent(average.secondary_enervate_bonus), self._fmt_bonus_percent(average.weakpoint_secondary_enervate_bonus))
            self._append(rows, "SECONDARY ENERVATE BONUS", "", "", bonus, when=float(average.secondary_enervate_bonus) > 0)
        section_breaks.append(averages_at)
        section_breaks.append(self._append_zone_metrics_section(rows, final))
        summary_rows = [(name, base, final) for name, base, _effective, final in rows]
        return self._table(("stat", "base", "final"), summary_rows, title=self._summary_title(selected), border="=", section_at=tuple(section_breaks))

    def _melee_summary(self) -> str:
        selected = self.weapon.results.main
        attack, base, effective, average, final = selected.attack, selected.base, selected.effective, selected.average, selected.final
        category = attack.category
        body_hit = hit_multiplier(average.crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        base_speed = attack.stats.fire_rate if attack.stats.attack_speed is None else attack.stats.attack_speed
        slam_damage = 1 + self._resolved_proportional(selected, "slam_damage")
        slide_crit = 1 + self._resolved_proportional(selected, "slide_crit_chance")

        rows: list[tuple[str, ...]] = []
        self._falloff_row(rows, selected)
        self._append(rows, "RANGE", self._fmt_meters(attack.stats.range), self._fmt_meters(effective.range), self._fmt_meters(effective.range), when=float(effective.range) > 0)
        self._append(rows, "ATTACK SPEED", self._fmt_multiplier(base_speed), self._fmt_multiplier(effective.attack_speed), self._fmt_multiplier(effective.attack_speed))
        self._append(rows, "CRIT CHANCE", self._fmt_percent(base.crit_chance), self._fmt_percent(effective.crit_chance), self._fmt_percent(average.crit_chance))
        self._append(rows, "CRIT DAMAGE", self._fmt_multiplier(base.crit_damage), self._fmt_multiplier(effective.crit_damage), self._fmt_multiplier(effective.crit_damage))
        self._append(rows, "STATUS CHANCE", self._fmt_percent(base.status_chance), self._fmt_percent(effective.status_chance), self._fmt_percent(effective.status_chance))
        self._append(rows, "INITIAL COMBO", "", self._fmt_number(effective.initial_combo), self._fmt_number(effective.initial_combo), when=float(effective.initial_combo) > 0)
        self._append(rows, "SLAM DAMAGE", "", self._fmt_multiplier(slam_damage), self._fmt_multiplier(slam_damage), when=category in SLAM_ATTACK_CATEGORIES and not isclose(slam_damage, 1))
        self._append(rows, "SLIDE CRIT CHANCE", "", self._fmt_multiplier(slide_crit), self._fmt_multiplier(slide_crit), when=category in SLIDE_ATTACK_CATEGORIES and not isclose(slide_crit, 1))

        section_breaks: list[int] = []
        damage_at = len(rows)
        self._append_damage_type_rows(rows, base.damage, effective.damage)
        self._append(rows, "TOTAL DAMAGE", self._fmt_number(base.damage.total), self._fmt_number(effective.damage.total), self._fmt_zone_metric(final.flat_dph, final.flat_weakpoint_dph, final.flat_resistant_dph))
        if damage_at < len(rows): section_breaks.append(damage_at)

        averages_at = len(rows)
        self._append(rows, "HIT MULTIPLIER", "", "", self._fmt_multiplier(body_hit))
        self._append_falloff_multiplier(rows, selected)
        self._append_damage_mass(rows, selected)
        self._append(rows, "EXPECTED PROCS PER HIT", "", "", self._fmt_number(average.procs_per_shot))
        self._append(rows, "COMBO MULTIPLIER", "", "", self._fmt_multiplier(average.combo_multiplier), when=category in HEAVY_ATTACK_CATEGORIES)
        self._append(rows, "MELEE DUPLICATE MULTIPLIER", "", "", self._fmt_multiplier(average.melee_duplicate_multiplier), when=not isclose(float(average.melee_duplicate_multiplier), 1))
        self._append(rows, "MELEE DOUGHTY BONUS", "", "", self._fmt_number(average.melee_doughty_bonus), when=float(average.melee_doughty_bonus) > 0)
        section_breaks.append(averages_at)
        section_breaks.append(self._append_zone_metrics_section(rows, final))
        summary_rows = [(name, base, final) for name, base, _effective, final in rows]
        return self._table(("stat", "base", "final"), summary_rows, title=self._summary_title(selected), border="=", section_at=tuple(section_breaks))
