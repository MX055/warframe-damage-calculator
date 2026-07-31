from __future__ import annotations

from typing import Callable, Literal
import re

from .analysis.contributions import progenitor_component_name, removal_contributions, shapley_contributions
from .domain.loadouts import Loadout
from .domain.perks import Perk
from .domain.results import CalculationResult, DamageMetrics, DamageResult, SpatialResult, StatusResult
from .domain.upgrades import Upgrade
from .domain.weapons import Weapon
from .engine.calculator import Calculator


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


class ResultFormatter:
    __slots__ = ("result",)

    def __init__(self, result: CalculationResult) -> None:
        self.result = result

    @staticmethod
    def _metric_name(metric: str) -> str:
        labels = {"direct": "Direct", "dot": "DoT", "total": "Total", "dph": "DPH", "dps": "DPS"}
        return " ".join(labels.get(part, part.title()) for part in metric.split("_"))

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
        if cls._visible_length(title) > inner_width:
            widths[-1] += cls._visible_length(title) - inner_width
            inner_width = cls._visible_length(title)
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

    def summary(self, attack: str | None = None) -> str:
        attack_name = self.result.selected_attack if attack is None else attack
        selected = self.result.attacks[attack_name]
        attack_definition = self.result.weapon.attacks[attack_name]
        average_damage = self.result.aggregate.average if attack is None else selected.average
        base, modded, effective, average = selected.base, selected.modded, selected.effective, selected.average
        rows: list[tuple[str, ...]] = [self._section("DAMAGE")]
        damage_types = dict.fromkeys((*base.damage, *modded.damage, *effective.damage))
        for damage_type in damage_types:
            rows.append((damage_type.replace("_", " ").title(), self._number(base.damage.get(damage_type, 0)), self._number(modded.damage.get(damage_type, 0)), self._number(effective.damage.get(damage_type, 0)), self._number(average.damage.get(damage_type, 0)), "—"))
        speed_label = "Attack Speed" if self.result.weapon.type == "melee" else "Fire Rate"
        rows.extend((
            self._section("OFFENSE"),
            ("Critical Chance", self._percent(base.crit_chance), self._percent(modded.crit_chance), self._percent(effective.crit_chance), self._percent(average.crit_chance), "—"),
            ("Critical Damage", self._multiplier(base.crit_damage), self._multiplier(modded.crit_damage), self._multiplier(effective.crit_damage), self._multiplier(average.crit_damage), "—"),
            ("Status Chance", self._percent(base.status_chance), self._percent(modded.status_chance), self._percent(effective.status_chance), self._percent(average.status_chance), "—"),
        ))
        if self.result.weapon.type != "melee": rows.append(("Multishot", self._multiplier(base.multishot), self._multiplier(modded.multishot), self._multiplier(effective.multishot), self._multiplier(average.multishot), "—"))
        rows.append((speed_label, self._attack_rate(base.fire_rate), self._attack_rate(modded.fire_rate), self._attack_rate(effective.fire_rate), self._attack_rate(average.fire_rate), "—"))
        if self.result.weapon.type != "melee":
            rows.extend((
                ("Magazine Capacity", self._rounds(base.get("magazine_capacity", self.result.weapon.magazine_size)), self._rounds(modded.get("magazine_capacity")), self._rounds(effective.get("magazine_capacity")), self._rounds(average.magazine_capacity), "—"),
                ("Reload Time", self._seconds(base.get("reload_time", self.result.weapon.reload_time)), self._seconds(modded.get("reload_time")), self._seconds(effective.get("reload_time")), self._seconds(average.reload_time), "—"),
                ("Ammo Cost", self._rounds(base.get("ammo_cost", attack_definition.stats.ammo_cost)), self._rounds(modded.get("ammo_cost")), self._rounds(effective.get("ammo_cost")), self._rounds(average.ammo_cost), "—"),
            ))
            if float(effective.get("punch_through", 0)) > 0: rows.append(("Punch Through", self._meters(base.get("punch_through", attack_definition.stats.punch_through)), self._meters(modded.get("punch_through")), self._meters(effective.get("punch_through")), self._meters(average.punch_through), "—"))
            if int(effective.get("burst_count", 1)) > 1: rows.append(("Burst Count", str(int(base.get("burst_count", attack_definition.stats.burst_count))), str(int(modded.get("burst_count", 1))), str(int(effective.get("burst_count"))), str(int(average.burst_count)), "—"))
            if float(effective.get("burst_delay", 0)) > 0: rows.append(("Burst Delay", self._seconds(base.get("burst_delay", attack_definition.stats.burst_delay)), self._seconds(modded.get("burst_delay")), self._seconds(effective.get("burst_delay")), self._seconds(average.burst_delay), "—"))
            if float(effective.get("charge_time", 0)) > 0: rows.append(("Charge Time", self._seconds(base.get("charge_time", attack_definition.stats.charge_time)), self._seconds(modded.get("charge_time")), self._seconds(effective.get("charge_time")), self._seconds(average.charge_time), "—"))
        rows.append(self._section("CALCULATED AVERAGES"))
        rows.append(("Attack Rate", "—", "—", "—", self._attack_rate(average.attack_rate), "—"))
        rows.append(("Expected Procs", "—", "—", "—", self._multiplier(selected.status.expected_procs_per_attack), "—"))
        if selected.spatial is not None: rows.append((f"Damage Mass (m{self._superscript(selected.spatial.dimension)})", "—", "—", "—", self._number(selected.spatial.damage_mass), "—"))
        rows.append(self._section("DAMAGE OUTPUT"))
        metrics = (("Direct DPH", "direct_dph"), ("DoT DPH", "dot_dph"), ("Total DPH", "total_dph"), ("Direct DPS", "direct_dps"), ("DoT DPS", "dot_dps"), ("Total DPS", "total_dps"))
        for label, attribute in metrics: rows.append((label, "—", "—", "—", self._number(getattr(average_damage, attribute)), "—"))
        weapon_name = getattr(self.result.weapon, "name", "Weapon")
        target_name = "" if self.result.target is None else f"vs {getattr(self.result.target, 'name', 'Target')} {self.result.selected_bodypart.replace('_', ' ').title()}"
        title = f"Summary: {weapon_name} {attack_name.replace('_', ' ').title()} {target_name}"
        return self._table(("Stat", "Base", "Modded", "Effective", "Average"), [tuple(cell for index, cell in enumerate(row) if index != 5) for row in rows], title=title)

    def contributions(self, metric: str = "total_dps", bodypart: str | None = None) -> str:
        selected_bodypart = bodypart or self.result.selected_bodypart
        calculator = Calculator(self.result.weapon, self.result.target)
        shapley = shapley_contributions(calculator, self.result.loadout, attack=self.result.selected_attack, metric=metric, bodypart=selected_bodypart, state=self.result.state)
        if not shapley: return ""
        removal = removal_contributions(calculator, self.result.loadout, attack=self.result.selected_attack, metric=metric, bodypart=selected_bodypart, state=self.result.state)
        component_types = {upgrade.name: upgrade.slot.replace("_", " ").title() for upgrade in self.result.loadout.upgrades}
        component_types.update({perk.name: "Perk" for perk in self.result.loadout.evolutions})
        if self.result.loadout.progenitor is not None: component_types[progenitor_component_name(self.result.loadout.progenitor)] = "Progenitor"
        maximum = max((abs(value) for value in shapley.values()), default=0)
        ordered = sorted(shapley.items(), key=lambda item: item[1], reverse=True)
        rows = []
        for rank, (name, share) in enumerate(ordered, 1):
            kind = component_types[name]
            removal_value = removal[name]
            display_share = 0.0 if share == 0 else share
            display_removal = 0.0 if removal_value == 0 else removal_value
            bar_length = 0 if maximum == 0 or share == 0 else max(1, round(abs(share) / maximum * 5))
            left = "·" * (10 - bar_length) + "█" * bar_length if share < 0 else "·" * 10
            right = "█" * bar_length + "·" * (10 - bar_length) if share > 0 else "·" * 10
            rows.append((str(rank), kind, name, f"{display_share:+.2%}", f"{display_removal:+,.2f}", f"{left}│{right}"))
        metric_name = self._metric_name(metric) if isinstance(metric, str) else "Contribution"
        target_name = "" if self.result.target is None else f" vs {getattr(self.result.target, 'name', 'Target')} {selected_bodypart.replace('_', ' ').title()}"
        title = f"{metric_name} Contributions: {self.result.weapon.name} {self.result.selected_attack.replace('_', ' ').title()}{target_name}"
        return self._table(("Contribution Rank", "Type", "Component", "Shapley", "Removal Difference", "Impact"), rows, title=title)

    def loadout(self) -> str:
        return format_loadout(self.result.loadout)

    def attack(self, name: str) -> str:
        return self.summary(name)

    def pool(self, pool: DamageResult) -> str:
        return format_damage_result(pool)

    def status(self, attack: str | None = None) -> str:
        status = self.result.aggregate.status if attack is None else self.result.attacks[attack].status
        return format_status(status)

    def spatial(self, attack: str) -> str:
        spatial = self.result.attacks[attack].spatial
        return "No spatial output" if spatial is None else format_spatial(spatial)


def format_result(result: CalculationResult, *, attack: str | None = None) -> str:
    return ResultFormatter(result).summary(attack)


def format_weapon(weapon: Weapon) -> str:
    attacks = ", ".join(weapon.attacks)
    perks = ", ".join(sorted((perk.name for perk in weapon.perks), key=str.casefold)) or "None"
    return f"{weapon.name}\nType: {weapon.type}\nSubtype: {weapon.subtype or '-'}\nAttacks: {attacks}\nPerks: {perks}"


def format_upgrade(upgrade: Upgrade) -> str:
    stats = ", ".join(upgrade.stats) or "None"
    return f"{upgrade.name}\nType: {upgrade.type}\nSlot: {upgrade.slot}\nStats: {stats}"


def format_perk(perk: Perk) -> str:
    stats = ", ".join(perk.stats) or "None"
    return f"{perk.name}\nStats: {stats}"


def format_loadout(loadout: Loadout) -> str:
    upgrades = "\n".join(f"- {upgrade.name}" for upgrade in loadout.upgrades) or "- None"
    evolutions = "\n".join(f"- {perk.name}" for perk in loadout.evolutions) or "- None"
    return f"Upgrades:\n{upgrades}\n\nEvolutions:\n{evolutions}"


def format_damage_result(result: DamageResult) -> str:
    return f"{result.total_dph:.2f} DPH, {result.total_dps:.2f} DPS"


def format_status(status: StatusResult) -> str:
    sustained = ", ".join(f"{name}={value:.2f}" for name, value in sorted(status.sustained_procs.items())) or "none"
    effects = ", ".join(f"{name}={value:.2f}" for name, value in sorted(status.effects.items())) or "none"
    return f"Expected procs per attack: {status.expected_procs_per_attack:.2f}\nSustained procs: {sustained}\nEffects: {effects}"


def format_spatial(spatial: SpatialResult) -> str:
    dimension = ResultFormatter._superscript(spatial.dimension)
    return f"Dimension: {spatial.dimension}\nDamage mass: {spatial.damage_mass:.2f} m{dimension}\nTotal DPS mass: {spatial.total_dps_mass:.2f}"
