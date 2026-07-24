from .weapon_formatter import WeaponFormatter
from ..calculators.weapon_calculator import WeaponCalculator
from ..utils.constants import HEAVY_ATTACK_CATEGORIES, SLAM_ATTACK_CATEGORIES, SLIDE_ATTACK_CATEGORIES


class MeleeFormatter(WeaponFormatter):
    def summary(self) -> str:
        selected = self.weapon.results.main
        base = selected.base
        effective = selected.effective
        average = selected.average
        final = selected.final
        category = selected.category
        hit_multiplier = WeaponCalculator._hit_multiplier(
            average.crit_chance,
            effective.crit_damage,
            effective.get("non_crit_bonus_damage", 0),
            effective.get("non_crit_bonus_chance", 0),
        )

        rows: list[tuple[str, ...]] = []
        self._append(rows, "RANGE", self._fmt_meters(base.get("range", 0)), self._fmt_meters(effective.get("range", 0)), self._fmt_meters(effective.get("range", 0)), when=float(effective.get("range", 0) or 0) > 0)
        self._append(rows, "ATTACK SPEED", self._fmt_multiplier(base.attack_speed), self._fmt_multiplier(effective.attack_speed), self._fmt_multiplier(effective.attack_speed))
        self._append(rows, "CRIT CHANCE", self._fmt_percent(base.crit_chance), self._fmt_percent(effective.crit_chance), self._fmt_percent(average.crit_chance))
        self._append(rows, "CRIT DAMAGE", self._fmt_multiplier(base.crit_damage), self._fmt_multiplier(effective.crit_damage), self._fmt_multiplier(effective.crit_damage))
        self._append(rows, "STATUS CHANCE", self._fmt_percent(base.status_chance), self._fmt_percent(effective.status_chance), self._fmt_percent(effective.status_chance))
        self._append(
            rows,
            "INITIAL COMBO",
            "",
            self._fmt_number(effective.get("initial_combo", 0)),
            self._fmt_number(effective.get("initial_combo", 0)),
            when=float(effective.get("initial_combo", 0) or 0) > 0,
        )
        self._append(
            rows,
            "SLAM DAMAGE",
            "",
            self._fmt_multiplier(effective.get("slam_damage", 1)),
            self._fmt_multiplier(effective.get("slam_damage", 1)),
            when=category in SLAM_ATTACK_CATEGORIES and float(effective.get("slam_damage", 1) or 1) != 1,
        )
        self._append(
            rows,
            "SLIDE CRIT CHANCE",
            "",
            self._fmt_multiplier(effective.get("slide_crit_chance", 1)),
            self._fmt_multiplier(effective.get("slide_crit_chance", 1)),
            when=category in SLIDE_ATTACK_CATEGORIES and float(effective.get("slide_crit_chance", 1) or 1) != 1,
        )

        section_breaks: list[int] = []
        damage_at = len(rows)
        self._append_damage_type_rows(rows, base.damage, effective.damage)
        self._append(
            rows,
            "TOTAL DAMAGE",
            self._fmt_number(base.damage.total_damage()),
            self._fmt_number(effective.damage.total_damage()),
            self._fmt_number(final.flat_dph),
        )
        if damage_at < len(rows):
            section_breaks.append(damage_at)

        averages_at = len(rows)
        self._append(rows, "HIT MULTIPLIER", "", "", self._fmt_multiplier(hit_multiplier))
        self._append(
            rows,
            "COMBO MULTIPLIER",
            "",
            "",
            self._fmt_multiplier(average.get("combo_multiplier", 1)),
            when=category in HEAVY_ATTACK_CATEGORIES,
        )
        self._append(rows, "MELEE DUPLICATE MULTIPLIER", "", "", self._fmt_multiplier(average.get("melee_duplicate_multiplier", 1)), when=float(average.get("melee_duplicate_multiplier", 1) or 1) != 1)
        self._append(rows, "MELEE DOUGHTY BONUS", "", "", self._fmt_number(average.get("melee_doughty_bonus", 0)), when=float(average.get("melee_doughty_bonus", 0) or 0) > 0)
        section_breaks.append(averages_at)

        dps_at = len(rows)
        self._append(rows, "FLAT DPH", "", "", self._fmt_number(final.flat_dph))
        self._append(rows, "FLAT DOTPH", "", "", self._fmt_number(final.flat_dotph))
        self._append(rows, "TOTAL DPH", "", "", self._fmt_number(final.total_dph))
        self._append(rows, "FLAT DPS", "", "", f"{self._fmt_number(final.flat_dps)} x BASE HPS")
        self._append(rows, "FLAT DOTPS", "", "", f"{self._fmt_number(final.flat_dotps)} x BASE HPS")
        self._append(rows, "TOTAL DPS", "", "", f"{self._fmt_number(final.total_dps)} x BASE HPS")
        section_breaks.append(dps_at)

        title = f"{self.weapon.data.name} - {selected.name.replace('_', ' ').title()}"
        return self._table(("stat", "base", "effective", "final"), rows, title=title, border="=", section_at=tuple(section_breaks))
