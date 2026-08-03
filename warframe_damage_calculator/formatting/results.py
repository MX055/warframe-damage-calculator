from __future__ import annotations

import re
from collections.abc import Callable

from ..domain.results import AttackSpatialMetrics, AttackStatusMetrics, CalculationResult, DamageResult
from ..engine.calculator import Calculator
from ..engine.metrics import balanced_damage_metric
from .objects import format_build


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


class Formatter:
    __slots__ = ("result",)

    def __init__(self, result: CalculationResult) -> None:
        self.result = result

    @staticmethod
    def _metric_label(metric: Callable) -> str:
        if metric is balanced_damage_metric: return "Balanced Damage"
        return getattr(metric, "__name__", "Contribution")

    @staticmethod
    def _number(value: object | None) -> str:
        return "—" if value is None else f"{float(value):,.2f}"

    @staticmethod
    def _percent(value: object | None) -> str:
        return "—" if value is None else f"{float(value):.2%}"

    @staticmethod
    def _multiplier(value: object | None) -> str:
        return "—" if value is None else f"{float(value):.2f}×"

    @staticmethod
    def _seconds(value: object | None) -> str:
        return "—" if value is None else f"{float(value):.2f}s"

    @staticmethod
    def _attack_rate(value: object | None) -> str:
        return "—" if value is None else f"{float(value):.2f}a/s"

    @staticmethod
    def _rounds(value: object | None) -> str:
        return "—" if value is None else f"{float(value):.0f}r"

    @staticmethod
    def _meters(value: object | None) -> str:
        return "—" if value is None else f"{float(value):g}m"

    @staticmethod
    def _superscript(value: int) -> str:
        return str(value).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))

    @staticmethod
    def _section(name: str, columns: int = 6) -> tuple[str, ...]:
        return (f"\0{name}", *("" for _ in range(columns - 1)))

    @staticmethod
    def _visible_length(value: str) -> int:
        return len(ANSI_PATTERN.sub("", value))

    @classmethod
    def _pad(cls, value: str, width: int) -> str:
        return value + " " * (width - cls._visible_length(value))

    @classmethod
    def _table(cls, headers: tuple[str, ...], rows: list[tuple[str, ...]], *, title: str) -> str:
        content_rows = [row for row in rows if not row[0].startswith("\0")]
        widths = [max(cls._visible_length(header), *(cls._visible_length(row[index]) for row in content_rows)) for index, header in enumerate(headers)]
        inner_width = sum(widths) + 3 * (len(widths) - 1) + 2
        title_len = cls._visible_length(title)
        # Title sits in "│ " ... " │", so it only has inner_width - 2 columns of content.
        overflow = title_len - (inner_width - 2)
        if overflow > 0:
            widths[-1] += overflow
            inner_width += overflow
        top = "┌" + "─" * inner_width + "┐"
        title_rule = "├" + "┬".join("─" * (width + 2) for width in widths) + "┤"
        header_rule = "├" + "┼".join("─" * (width + 2) for width in widths) + "┤"
        bottom = "└" + "┴".join("─" * (width + 2) for width in widths) + "┘"
        values = [top, "│ " + cls._pad(title, inner_width - 2) + " │", title_rule]
        values.append("│ " + " │ ".join(cls._pad(header, widths[index]) for index, header in enumerate(headers)) + " │")
        values.append(header_rule)
        has_content = False
        for row in rows:
            if row[0].startswith("\0"):
                if has_content and values[-1] != header_rule: values.append(header_rule)
                continue
            values.append("│ " + " │ ".join(cls._pad(cell, widths[index]) for index, cell in enumerate(row)) + " │")
            has_content = True
        values.append(bottom)
        return "\n".join(values)

    def stat_summary_table(self) -> tuple[str, tuple[str, ...], list[tuple[str, ...]]]:
        attack_name = self.result.selected_attack
        selected = self.result.attacks[attack_name]
        attack_definition = self.result.weapon.attacks[attack_name]
        output_damage = self.result.aggregate.damage
        base, modded, effective = selected.base, selected.modded, selected.effective
        damage, critical, timing, status, spatial = selected.damage, selected.critical, selected.timing, selected.status, selected.spatial
        rows: list[tuple[str, ...]] = [self._section("DAMAGE")]
        damage_types = dict.fromkeys((*base.damage, *modded.damage, *effective.damage))
        for damage_type in damage_types:
            rows.append((damage_type.replace("_", " ").title(), self._number(base.damage.get(damage_type, 0)), self._number(modded.damage.get(damage_type, 0)), self._number(effective.damage.get(damage_type, 0)), self._number(damage.damage.get(damage_type, 0)), "—"))
        speed_label = "Attack Speed" if self.result.weapon.type == "melee" else "Fire Rate"
        rows.extend((
            self._section("OFFENSE"),
            ("Critical Chance", self._percent(base.crit_chance), self._percent(modded.crit_chance), self._percent(effective.crit_chance), self._percent(critical.crit_chance), "—"),
            ("Critical Damage", self._multiplier(base.crit_damage), self._multiplier(modded.crit_damage), self._multiplier(effective.crit_damage), self._multiplier(critical.crit_damage), "—"),
            ("Status Chance", self._percent(base.status_chance), self._percent(modded.status_chance), self._percent(effective.status_chance), self._percent(status.status_chance), "—"),
        ))
        if self.result.weapon.type != "melee": rows.append(("Multishot", self._multiplier(base.multishot), self._multiplier(modded.multishot), self._multiplier(effective.multishot), self._multiplier(timing.multishot), "—"))
        rows.append((speed_label, self._attack_rate(base.fire_rate), self._attack_rate(modded.fire_rate), self._attack_rate(effective.fire_rate), self._attack_rate(timing.fire_rate), "—"))
        if self.result.weapon.type != "melee":
            rows.extend((
                ("Magazine Capacity", self._rounds(base.get("magazine_capacity", self.result.weapon.magazine_size)), self._rounds(modded.get("magazine_capacity")), self._rounds(effective.get("magazine_capacity")), self._rounds(timing.magazine_capacity), "—"),
                ("Reload Time", self._seconds(base.get("reload_time", self.result.weapon.reload_time)), self._seconds(modded.get("reload_time")), self._seconds(effective.get("reload_time")), self._seconds(timing.reload_time), "—"),
                ("Ammo Cost", self._rounds(base.get("ammo_cost", attack_definition.stats.ammo_cost)), self._rounds(modded.get("ammo_cost")), self._rounds(effective.get("ammo_cost")), self._rounds(timing.ammo_cost), "—"),
            ))
            if float(effective.get("punch_through", 0)) > 0: rows.append(("Punch Through", self._meters(base.get("punch_through", attack_definition.stats.punch_through)), self._meters(modded.get("punch_through")), self._meters(effective.get("punch_through")), self._meters(spatial.punch_through), "—"))
            if int(effective.get("burst_count", 1)) > 1: rows.append(("Burst Count", str(int(base.get("burst_count", attack_definition.stats.burst_count))), str(int(modded.get("burst_count", 1))), str(int(effective.get("burst_count"))), str(int(timing.burst_count)), "—"))
            if float(effective.get("burst_delay", 0)) > 0: rows.append(("Burst Delay", self._seconds(base.get("burst_delay", attack_definition.stats.burst_delay)), self._seconds(modded.get("burst_delay")), self._seconds(effective.get("burst_delay")), self._seconds(timing.burst_delay), "—"))
            if float(effective.get("charge_time", 0)) > 0: rows.append(("Charge Time", self._seconds(base.get("charge_time", attack_definition.stats.charge_time)), self._seconds(modded.get("charge_time")), self._seconds(effective.get("charge_time")), self._seconds(timing.charge_time), "—"))
        rows.append(self._section("CALCULATED AVERAGES"))
        rows.append(("Attack Rate", "—", "—", "—", self._attack_rate(timing.attack_rate), "—"))
        rows.append(("Expected Procs", "—", "—", "—", self._multiplier(status.expected_procs_per_attack), "—"))
        if spatial.damage_mass is not None: rows.append(("Damage Mass", "—", "—", "—", f"{self._number(spatial.damage_mass)}m{self._superscript(spatial.dimension)}", "—"))
        rows.append(self._section("DAMAGE OUTPUT"))
        metrics = (("Direct DPH", "direct_dph"), ("DoT DPH", "dot_dph"), ("Total DPH", "total_dph"), ("Direct DPS", "direct_dps"), ("DoT DPS", "dot_dps"), ("Total DPS", "total_dps"))
        for label, attribute in metrics: rows.append((label, "—", "—", "—", self._number(getattr(output_damage, attribute)), "—"))
        weapon_name = getattr(self.result.weapon, "name", "Weapon")
        target_name = "" if self.result.target is None else f"vs {self.result.target.name} {self.result.target.body_parts[self.result.selected_body_part].name}"
        title = f"Summary: {weapon_name} {self.result.weapon.attacks[attack_name].name} {target_name}"
        headers = ("Stat", "Base", "Modded", "Effective", "Average")
        display_rows = [tuple(cell for index, cell in enumerate(row) if index != 5) for row in rows]
        return title, headers, display_rows

    def stat_summary(self) -> str:
        title, headers, rows = self.stat_summary_table()
        return self._table(headers, rows, title=title)

    def build_summary_table(self, metric: Callable = balanced_damage_metric, contributions=None) -> tuple[str, tuple[str, ...], list[tuple[str, ...]]] | None:
        selected_body_part = self.result.selected_body_part
        if contributions is None:
            contributions = Calculator(self.result.weapon, self.result.target, self.result.build).contributions(attack=self.result.selected_attack, metric=metric, body_part=selected_body_part, state=self.result.state)
        contribution = contributions.contribution
        if not contribution: return None
        removal = contributions.removal
        component_types = {upgrade.name: upgrade.slot.replace("_", " ").title() for upgrade in self.result.build.ranked_upgrades}
        component_types.update({perk.name: "Perk" for perk in self.result.build.evolutions})
        if self.result.build.progenitor is not None:
            for name in contribution:
                if name not in component_types: component_types[name] = "Progenitor"
        maximum = max((abs(value) for value in contribution.values()), default=0)
        ordered = sorted(contribution.items(), key=lambda item: item[1], reverse=True)
        rows = []
        for rank, (name, share) in enumerate(ordered, 1):
            kind = component_types[name]
            display_name = "Riven" if kind == "Regular Mod" and name.casefold().startswith("riven (") else name
            if kind == "Progenitor": display_name = f"{self.result.build.progenitor.element.replace('_', ' ').title()} Progenitor"
            removal_value = removal[name]
            display_share = 0.0 if share == 0 else share
            display_removal = 0.0 if removal_value == 0 else removal_value
            bar_length = 0 if maximum == 0 or share == 0 else max(1, round(abs(share) / maximum * 5))
            left = "·" * (10 - bar_length) + "█" * bar_length if share < 0 else "·" * 10
            right = "█" * bar_length + "·" * (10 - bar_length) if share > 0 else "·" * 10
            rows.append((str(rank), kind, display_name, f"{display_share:+.2%}", f"{display_removal:+,.2f}", f"{left}│{right}"))
        metric_name = self._metric_label(metric)
        target_name = "" if self.result.target is None else f" vs {self.result.target.name} {self.result.target.body_parts[selected_body_part].name}"
        title = f"{metric_name} Contributions: {self.result.weapon.name} {self.result.weapon.attacks[self.result.selected_attack].name}{target_name}"
        return title, ("Contribution Rank", "Type", "Component", "Relative Contribution", "Removal Difference", "Impact"), rows

    def build_summary(self, metric: Callable = balanced_damage_metric) -> str:
        table = self.build_summary_table(metric=metric)
        if table is None: return ""
        title, headers, rows = table
        return self._table(headers, rows, title=title)

    def build(self) -> str:
        return format_build(self.result.build)

    def pool(self, pool: DamageResult) -> str:
        return format_damage_result(pool)

    def status_summary(self) -> str:
        return "\n".join(self.status_summary_table()[1])

    def status_summary_table(self) -> tuple[str, list[str]]:
        attacks = [(key, self.result.weapon.attacks[key].name if key in self.result.weapon.attacks else key.replace("_", " ").title(), calculated) for key, calculated in self.result.attacks.items()]
        type_order = ("impact", "puncture", "slash", "heat", "cold", "electricity", "toxin", "blast", "radiation", "gas", "magnetic", "viral", "corrosive", "void")
        present: set[str] = set()
        for _, _, calculated in attacks:
            damage = calculated.effective.damage
            forced = calculated.effective.forced_procs
            model = calculated.effective.status_model
            present.update(kind for kind in type_order if damage.get(kind, 0) or forced.get(kind, 0) or model.proc_count_per_attack(kind))
            present.update(kind for kind in (*damage, *forced) if kind not in type_order)
        damage_types = [kind for kind in type_order if kind in present] + sorted(present - set(type_order))
        subheaders = ("Damage", "Weight", "Forced Procs", "Proc Rate")
        left_header = "Damage Type"
        left_width = max(self._visible_length(left_header), *(self._visible_length(kind.replace("_", " ").title()) for kind in damage_types), 1)
        groups: list[tuple[str, list[int], list[tuple[str, str, str, str]]]] = []
        for _, attack_name, calculated in attacks:
            damage = calculated.effective.damage
            forced = calculated.effective.forced_procs
            model = calculated.effective.status_model
            total = float(damage.total)
            rows: list[tuple[str, str, str, str]] = []
            widths = [self._visible_length(header) for header in subheaders]
            for kind in damage_types:
                amount = float(damage.get(kind, 0))
                forced_amount = float(forced.get(kind, 0))
                procs = float(model.proc_count_per_attack(kind))
                weight = 0.0 if total <= 0 or amount <= 0 else amount / total
                cells = (
                    self._number(amount) if amount else "—",
                    self._number(weight) if weight else "—",
                    self._number(forced_amount) if forced_amount else "—",
                    self._percent(procs) if procs else "—",
                )
                rows.append(cells)
                for index, cell in enumerate(cells): widths[index] = max(widths[index], self._visible_length(cell))
            span = sum(widths) + 3 * (len(widths) - 1)
            overflow = self._visible_length(attack_name) - span
            if overflow > 0: widths[-1] += overflow
            groups.append((attack_name, widths, rows))
        if not groups:
            groups.append(("—", [self._visible_length(header) for header in subheaders], []))
            damage_types = []
        top = "┌" + "─" * (left_width + 2) + "".join("┬" + "─" * (sum(widths) + 3 * (len(widths) - 1) + 2) for _, widths, _ in groups) + "┐"
        attack_row = "│ " + self._pad("", left_width) + " │ " + " │ ".join(self._pad(name, sum(widths) + 3 * (len(widths) - 1)) for name, widths, _ in groups) + " │"
        split = "│ " + self._pad(left_header, left_width) + " ├" + "┼".join("┬".join("─" * (width + 2) for width in widths) for _, widths, _ in groups) + "┤"
        subheader_row = "│ " + self._pad("", left_width) + " │ " + " │ ".join(" │ ".join(self._pad(header, widths[index]) for index, header in enumerate(subheaders)) for _, widths, _ in groups) + " │"
        header_rule = "├" + "─" * (left_width + 2) + "".join("┼" + "┼".join("─" * (width + 2) for width in widths) for _, widths, _ in groups) + "┤"
        bottom = "└" + "─" * (left_width + 2) + "".join("┴" + "┴".join("─" * (width + 2) for width in widths) for _, widths, _ in groups) + "┘"
        lines = [top, attack_row, split, subheader_row, header_rule]
        for row_index, kind in enumerate(damage_types):
            label = kind.replace("_", " ").title()
            cells = " │ ".join(" │ ".join(self._pad(group[2][row_index][index], group[1][index]) for index in range(4)) for group in groups)
            lines.append("│ " + self._pad(label, left_width) + " │ " + cells + " │")
        lines.append(bottom)
        weapon_name = getattr(self.result.weapon, "name", "Weapon")
        target_name = "" if self.result.target is None else f" vs {self.result.target.name} {self.result.target.body_parts[self.result.selected_body_part].name}"
        title = f"Status: {weapon_name}{target_name}"
        return title, lines

    def spatial(self, attack: str) -> str:
        spatial = self.result.attacks[attack].spatial
        return "No spatial output" if spatial.damage_mass is None else format_spatial(spatial)


def format_result(result: CalculationResult) -> str:
    return Formatter(result).stat_summary()


def format_damage_result(result: DamageResult) -> str:
    return f"{result.total_dph:.2f} DPH, {result.total_dps:.2f} DPS"


def format_status(status: AttackStatusMetrics) -> str:
    sustained = ", ".join(f"{name}={value:.2f}" for name, value in sorted(status.sustained_procs.items())) or "none"
    effects = ", ".join(f"{name}={value:.2f}" for name, value in sorted(status.effects.items())) or "none"
    return f"Expected procs per attack: {status.expected_procs_per_attack:.2f}\nSustained procs: {sustained}\nEffects: {effects}"


def format_spatial(spatial: AttackSpatialMetrics) -> str:
    if spatial.dimension is None or spatial.damage_mass is None or spatial.total_dps_mass is None: return "No spatial output"
    dimension = Formatter._superscript(spatial.dimension)
    return f"Dimension: {spatial.dimension}\nDamage mass: {spatial.damage_mass:.2f} m{dimension}\nTotal DPS mass: {spatial.total_dps_mass:.2f}"
