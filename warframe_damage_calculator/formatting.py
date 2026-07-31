from __future__ import annotations

from typing import Callable
import re

from .analysis.contributions import removal_contributions, shapley_contributions
from .domain.loadouts import Loadout
from .domain.perks import Perk
from .domain.results import CalculationResult, DamageMetrics, DamageResult, SpatialResult, StatusResult
from .domain.upgrades import Upgrade
from .domain.weapons import Weapon
from .engine.calculator import Calculator


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
GREEN = "\x1b[32m"
RED = "\x1b[31m"
RESET = "\x1b[0m"


class ResultFormatter:
    __slots__ = ("result",)

    def __init__(self, result: CalculationResult) -> None:
        self.result = result

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
    def _rounds(value: object | None) -> str:
        return "—" if value is None else f"{float(value):.0f}r"

    @staticmethod
    def _meters(value: object | None) -> str:
        return "—" if value is None else f"{float(value):g}m"

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
        line = " │ ".join(cls._pad(header, widths[index]) for index, header in enumerate(headers))
        rule = "─" * cls._visible_length(line)
        values = [title, rule, line, rule]
        for row in rows:
            if row[0].startswith("\0"):
                if values[-1] != rule: values.append(rule)
                continue
            values.append(" │ ".join(cls._pad(cell, widths[index]) for index, cell in enumerate(row)))
        values.append(rule)
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
            rows.append((damage_type.replace("_", " ").title(), self._number(base.damage.get(damage_type, 0)), self._number(modded.damage.get(damage_type, 0)), self._number(effective.damage.get(damage_type, 0)), "—", "—"))
        rows.extend((
            self._section("OFFENSE"),
            ("Critical Chance", self._percent(base.crit_chance), self._percent(modded.crit_chance), self._percent(effective.crit_chance), self._percent(average.crit_chance), "—"),
            ("Critical Damage", self._multiplier(base.crit_damage), self._multiplier(modded.crit_damage), self._multiplier(effective.crit_damage), "—", "—"),
            ("Status Chance", self._percent(base.status_chance), self._percent(modded.status_chance), self._percent(effective.status_chance), "—", "—"),
            ("Multishot", self._multiplier(base.multishot), self._multiplier(modded.multishot), self._multiplier(effective.multishot), "—", "—"),
            ("Fire Rate", self._number(base.fire_rate), self._number(modded.fire_rate), self._number(effective.instantaneous_fire_rate), self._number(average.sustained_fire_rate), "—"),
            ("Expected Procs", "—", "—", "—", self._number(selected.status.expected_procs_per_attack), "—"),
            self._section("HANDLING"),
            ("Magazine Capacity", self._rounds(self.result.weapon.magazine_size), "—", self._rounds(effective.get("magazine_capacity")), "—", "—"),
            ("Reload Time", self._seconds(self.result.weapon.reload_time), "—", self._seconds(effective.get("reload_time")), "—", "—"),
            ("Ammo Cost", self._number(attack_definition.stats.ammo_cost), "—", self._number(effective.get("ammo_cost")), "—", "—"),
        ))
        if float(effective.get("punch_through", 0)) > 0: rows.append(("Punch Through", self._meters(attack_definition.stats.punch_through), "—", self._meters(effective.get("punch_through")), "—", "—"))
        if int(effective.get("burst_count", 1)) > 1: rows.append(("Burst Count", str(int(attack_definition.stats.burst_count)), "—", str(int(effective.get("burst_count"))), "—", "—"))
        if float(effective.get("burst_delay", 0)) > 0: rows.append(("Burst Delay", self._seconds(attack_definition.stats.burst_delay), "—", self._seconds(effective.get("burst_delay")), "—", "—"))
        if float(effective.get("charge_time", 0)) > 0: rows.append(("Charge Time", self._seconds(attack_definition.stats.charge_time), "—", self._seconds(effective.get("charge_time")), "—", "—"))
        rows.append(self._section("DAMAGE OUTPUT"))
        metrics = (("DIRECT DPH", "direct_dph"), ("DOT DPH", "dot_dph"), ("TOTAL DPH", "total_dph"), ("DIRECT DPS", "direct_dps"), ("DOT DPS", "dot_dps"), ("TOTAL DPS", "total_dps"))
        zones = (("Normal", average_damage.normal), ("Weakpoint", average_damage.weakpoint), ("Resistant", average_damage.resistant))
        for label, attribute in metrics:
            for zone_name, zone in zones:
                if zone is None: continue
                rows.append((f"{label} — {zone_name}", "—", "—", "—", self._number(getattr(zone, attribute)), "—"))
        if selected.spatial is not None:
            rows.extend((self._section("SPATIAL"), (f"Damage Mass (m^{selected.spatial.dimension})", "—", "—", "—", self._number(selected.spatial.damage_mass), "—")))
        weapon_name = getattr(self.result.weapon, "name", "Weapon")
        target_name = "" if self.result.target is None else f" vs {getattr(self.result.target, 'name', 'Target')}"
        title = f"{weapon_name} · {attack_name.replace('_', ' ').title()}{target_name}"
        return self._table(("Stat", "Base", "Modded", "Effective", "Average"), [tuple(cell for index, cell in enumerate(row) if index != 5) for row in rows], title=title)

    def contributions(self, metric: str = "total_dps") -> str:
        calculator = Calculator(self.result.weapon, self.result.target)
        shapley = shapley_contributions(calculator, self.result.loadout, attack=self.result.selected_attack, metric=metric, state=self.result.state)
        if not shapley: return ""
        removal = removal_contributions(calculator, self.result.loadout, attack=self.result.selected_attack, metric=metric, state=self.result.state)
        upgrade_names = {upgrade.name for upgrade in self.result.loadout.upgrades}
        maximum = max((abs(value) for value in shapley.values()), default=0)
        ordered = sorted(shapley.items(), key=lambda item: item[1], reverse=True)
        rows = []
        for rank, (name, share) in enumerate(ordered, 1):
            kind = "Upgrade" if name in upgrade_names else "Evolution"
            bar_length = 0 if maximum == 0 or share == 0 else max(1, round(abs(share) / maximum * 5))
            bar = "" if bar_length == 0 else f"{RED if share < 0 else GREEN}{'█' * bar_length}{RESET}"
            rows.append((str(rank), kind, name, f"{share:.2%}", f"{removal[name]:,.2f}", bar))
        metric_name = metric.replace("_", " ").upper() if isinstance(metric, str) else "Contribution"
        target_name = "" if self.result.target is None else f" vs {getattr(self.result.target, 'name', 'Target')}"
        title = f"{self.result.weapon.name} · {self.result.selected_attack.replace('_', ' ').title()}{target_name} · {metric_name} Contributions"
        return self._table(("Rank", "Type", "Component", "Shapley", f"{metric_name} Loss", "Impact"), rows, title=title)

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
    return f"{upgrade.name}\nKind: {upgrade.kind}\nSlot: {upgrade.slot}\nStats: {stats}"


def format_perk(perk: Perk) -> str:
    stats = ", ".join(perk.stats) or "None"
    return f"{perk.name}\nStats: {stats}"


def format_loadout(loadout: Loadout) -> str:
    upgrades = "\n".join(f"- {upgrade.name}" for upgrade in loadout.upgrades) or "- None"
    evolutions = "\n".join(f"- {perk.name}" for perk in loadout.evolutions) or "- None"
    return f"Upgrades:\n{upgrades}\n\nEvolutions:\n{evolutions}"


def format_damage_result(result: DamageResult) -> str:
    zones = (("normal", result.normal), ("weakpoint", result.weakpoint), ("resistant", result.resistant))
    return "\n".join(f"{name}: {metrics.total_dph:.2f} DPH, {metrics.total_dps:.2f} DPS" for name, metrics in zones if metrics is not None)


def format_status(status: StatusResult) -> str:
    sustained = ", ".join(f"{name}={value:.2f}" for name, value in sorted(status.sustained_procs.items())) or "none"
    effects = ", ".join(f"{name}={value:.2f}" for name, value in sorted(status.effects.items())) or "none"
    return f"Expected procs per attack: {status.expected_procs_per_attack:.2f}\nSustained procs: {sustained}\nEffects: {effects}"


def format_spatial(spatial: SpatialResult) -> str:
    return f"Dimension: {spatial.dimension}\nDamage mass: {spatial.damage_mass:.2f} m^{spatial.dimension}\nTotal DPS mass: {spatial.normal.total_dps_mass:.2f}"
