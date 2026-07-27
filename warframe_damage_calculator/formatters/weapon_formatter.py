from ..core.dist import Dist
from ..protocols import WeaponFormatterOwner
from ..utils.types import Number


class WeaponFormatter:
    def __init__(self, weapon: WeaponFormatterOwner) -> None:
        self.weapon = weapon

    @staticmethod
    def _with_weakpoint(value: str | None, weakpoint: str | None = None) -> str:
        if value is None: return weakpoint or ""
        return value if weakpoint is None else f"{value} | {weakpoint}"

    def _with_hit_zones(self, normal: str | None, weakpoint: str | None, resistant: str | None) -> str:
        if getattr(self.weapon, "target", None) is None: return self._with_weakpoint(normal, weakpoint)
        return " | ".join(value for value in (normal, weakpoint, resistant) if value is not None)

    @staticmethod
    def _fmt_number(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):.2f}"

    @staticmethod
    def _fmt_percent(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):.2%}"

    @staticmethod
    def _fmt_bonus_percent(value: Number | None) -> str | None:
        return None if value is None else f"+{float(value):.2%}"

    @staticmethod
    def _fmt_multiplier(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):.2f}x"

    @staticmethod
    def _fmt_rate(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):.2f}rps"

    @staticmethod
    def _fmt_seconds(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):.2f}s"

    @staticmethod
    def _fmt_rounds(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):.0f}r"

    @staticmethod
    def _fmt_meters(value: Number | None) -> str | None:
        return None if value is None else f"{float(value):g}m"

    def _hit_zone_label(self) -> str:
        target = getattr(self.weapon, "target", None)
        if target is None: return "normal | weakpoint"
        zones = ("normal", "weakpoint", "resistant")
        present = [zone for zone in zones if any(part.type == zone for part in target.data.bodyparts.values())]
        return " | ".join(present)

    def _summary_title(self, selected) -> str:
        title = f"{self.weapon.data.name} - {selected.name.replace('_', ' ').title()}"
        if self.weapon.target is not None: title += f" vs {self.weapon.target.data.name} (bodypart: {self._hit_zone_label()})"
        return title

    def _fmt_zone_metric(self, normal, weakpoint, resistant) -> str:
        return self._with_hit_zones(self._fmt_number(normal), self._fmt_number(weakpoint), self._fmt_number(resistant))

    def _append_zone_metrics_section(self, rows: list[tuple[str, ...]], final) -> int:
        section_at = len(rows)
        self._append(rows, "FLAT DPH", "", "", self._fmt_zone_metric(final.flat_dph, final.flat_weakpoint_dph, final.flat_resistant_dph))
        self._append(rows, "FLAT DOTPH", "", "", self._fmt_zone_metric(final.flat_dotph, final.flat_weakpoint_dotph, final.flat_resistant_dotph))
        self._append(rows, "TOTAL DPH", "", "", self._fmt_zone_metric(final.total_dph, final.total_weakpoint_dph, final.total_resistant_dph))
        self._append(rows, "FLAT DPS", "", "", self._fmt_zone_metric(final.flat_dps, final.flat_weakpoint_dps, final.flat_resistant_dps))
        self._append(rows, "FLAT DOTPS", "", "", self._fmt_zone_metric(final.flat_dotps, final.flat_weakpoint_dotps, final.flat_resistant_dotps))
        self._append(rows, "TOTAL DPS", "", "", self._fmt_zone_metric(final.total_dps, final.total_weakpoint_dps, final.total_resistant_dps))
        return section_at

    @staticmethod
    def _attack_label(name: str) -> str:
        return name.replace("_", " ").upper()

    def _append_damage_type_rows(self, rows: list[tuple[str, ...]], base_damage: Dist, effective_damage: Dist, *, prefix: str = "") -> None:
        damage_types = dict.fromkeys((*base_damage.data, *effective_damage.data))
        for damage_type in damage_types:
            label = f"{prefix}{damage_type.upper()}".strip()
            self._append(
                rows,
                label,
                self._fmt_number(base_damage.get(damage_type, 0)),
                self._fmt_number(effective_damage.get(damage_type, 0)),
                self._fmt_number(effective_damage.get(damage_type, 0)),
            )

    @staticmethod
    def _append(rows: list[tuple[str, ...]], name: str, base: str = "", effective: str = "", average: str = "", *, when: bool = True) -> None:
        if when:
            rows.append((name, base, effective, average))

    @staticmethod
    def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]], *, title: str | None = None, section_at: int | tuple[int, ...] | None = None, border: str | None = None) -> str:
        widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
        breaks = set() if section_at is None else {section_at} if isinstance(section_at, int) else set(section_at)

        def format_row(cells: tuple[str, ...]) -> str:
            return " | ".join(f"{cell:<{widths[index]}}" for index, cell in enumerate(cells))

        header = format_row(headers)
        rule = "-" * len(header)
        lines = []
        if title:
            lines.append(title)
        if border:
            lines.append(border * len(header))
        lines.append(header)
        lines.append(rule)
        for index, row in enumerate(rows):
            if index in breaks:
                lines.append(rule)
            lines.append(format_row(row))
        if border:
            lines.append(border * len(header))
        return "\n".join(lines)

    def _falloff_row(self, rows: list[tuple[str, ...]], base, effective) -> None:
        if "start_range" not in base:
            return
        def format_falloff(stats) -> str:
            return f"{float(stats.start_range):g}m -> {float(stats.end_range):g}m @ {float(stats.final_multiplier):.2%}"

        base_text = format_falloff(base)
        effective_text = format_falloff(effective if "start_range" in effective else base)
        self._append(rows, "FALLOFF", base_text, effective_text, effective_text)

    def upgrades(self) -> str:
        shapley = self.weapon.results.shapley_contributions()
        if not shapley:
            return ""
        removal = self.weapon.results.removal_contributions()
        rows = [(name, f"{share:.2%}", f"{removal[name]:.2f}") for name, share in shapley.items()]
        title = f"{self.weapon.data.name} - {self.weapon.results.main.name.replace('_', ' ').title()}"
        return self._table(("upgrade", "shapley", "removal"), rows, title=title, border="=")

    def summary(self) -> str:
        raise NotImplementedError
