from __future__ import annotations

from typing import Callable

from .analysis.contributions import removal_contributions, shapley_contributions
from .domain.loadouts import Loadout
from .domain.perks import Perk
from .domain.results import CalculationResult, DamageMetrics, DamageResult, SpatialResult, StatusResult
from .domain.upgrades import Upgrade
from .domain.weapons import Weapon
from .engine.calculator import Calculator


class ResultFormatter:
    __slots__ = ("result",)

    def __init__(self, result: CalculationResult) -> None:
        self.result = result

    @staticmethod
    def _number(value: object | None) -> str:
        return "-" if value is None else f"{float(value):.2f}"

    @staticmethod
    def _percent(value: object | None) -> str:
        return "-" if value is None else f"{float(value):.2%}"

    @staticmethod
    def _multiplier(value: object | None) -> str:
        return "-" if value is None else f"{float(value):.2f}x"

    @staticmethod
    def _zones(final: DamageResult, getter: Callable[[DamageMetrics], float]) -> str:
        values = [getter(final.normal)]
        if final.weakpoint is not None: values.append(getter(final.weakpoint))
        if final.resistant is not None: values.append(getter(final.resistant))
        return " | ".join(f"{value:.2f}" for value in values)

    @staticmethod
    def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]], *, title: str) -> str:
        widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
        line = " | ".join(f"{header:<{widths[index]}}" for index, header in enumerate(headers))
        rule = "-" * len(line)
        values = [title, "=" * len(line), line, rule]
        values.extend(" | ".join(f"{cell:<{widths[index]}}" for index, cell in enumerate(row)) for row in rows)
        values.append("=" * len(line))
        return "\n".join(values)

    def summary(self, attack: str | None = None) -> str:
        selected = self.result.attacks[self.result.selected_attack] if attack is None else self.result.attacks[attack]
        final = self.result.aggregate.final if attack is None else selected.final
        base, modded, effective, average = selected.base, selected.modded, selected.effective, selected.average
        rows: list[tuple[str, ...]] = []
        damage_types = dict.fromkeys((*base.damage, *modded.damage, *effective.damage))
        for damage_type in damage_types: rows.append((damage_type.upper(), self._number(base.damage.get(damage_type, 0)), self._number(modded.damage.get(damage_type, 0)), self._number(effective.damage.get(damage_type, 0)), "", ""))
        rows.append(("DIRECT DPH", "", "", "", self._number(average.normal.direct_dph), self._zones(final, lambda zone: zone.direct_dph)))
        rows.append(("DOT DPH", "", "", "", self._number(average.normal.dot_dph), self._zones(final, lambda zone: zone.dot_dph)))
        rows.append(("TOTAL DPH", "", "", "", self._number(average.normal.total_dph), self._zones(final, lambda zone: zone.total_dph)))
        rows.append(("DIRECT DPS", "", "", "", self._number(average.normal.direct_dps), self._zones(final, lambda zone: zone.direct_dps)))
        rows.append(("DOT DPS", "", "", "", self._number(average.normal.dot_dps), self._zones(final, lambda zone: zone.dot_dps)))
        rows.append(("TOTAL DPS", "", "", "", self._number(average.normal.total_dps), self._zones(final, lambda zone: zone.total_dps)))
        rows.append(("CRIT CHANCE", self._percent(base.crit_chance), self._percent(modded.crit_chance), self._percent(effective.crit_chance), self._percent(average.crit_chance), ""))
        rows.append(("CRIT DAMAGE", self._multiplier(base.crit_damage), self._multiplier(modded.crit_damage), self._multiplier(effective.crit_damage), self._multiplier(average.crit_multiplier), ""))
        rows.append(("STATUS CHANCE", self._percent(base.status_chance), self._percent(modded.status_chance), self._percent(effective.status_chance), "", ""))
        rows.append(("MULTISHOT", self._multiplier(base.multishot), self._multiplier(modded.multishot), self._multiplier(effective.multishot), "", ""))
        rows.append(("FIRE RATE", self._number(base.fire_rate), self._number(modded.get("fire_rate")), self._number(effective.instantaneous_fire_rate), self._number(average.sustained_fire_rate), ""))
        rows.append(("RELOAD TIME", self._number(self.result.weapon.reload_time), "", self._number(effective.reload_time), "", ""))
        rows.append(("MAGAZINE CAPACITY", self._number(self.result.weapon.magazine_size), "", self._number(effective.get("magazine_capacity")), "", ""))
        rows.append(("AMMO COST", self._number(selected.attack.stats.ammo_cost), "", self._number(effective.get("ammo_cost")), "", ""))
        rows.append(("PUNCH THROUGH", self._number(selected.attack.stats.punch_through), "", self._number(effective.get("punch_through")), "", ""))
        rows.append(("BURST COUNT", self._number(selected.attack.stats.burst_count), "", self._number(effective.get("burst_count")), "", ""))
        rows.append(("BURST DELAY", self._number(selected.attack.stats.burst_delay), "", self._number(effective.get("burst_delay")), "", ""))
        rows.append(("CHARGE TIME", self._number(selected.attack.stats.charge_time), "", self._number(effective.get("charge_time")), "", ""))
        rows.append(("EXPECTED PROCS", "", "", "", self._number(selected.status.expected_procs_per_attack), ""))
        if selected.spatial is not None: rows.append((f"DAMAGE MASS (m^{selected.spatial.dimension})", "", "", "", "", self._number(selected.spatial.damage_mass)))
        weapon_name = getattr(self.result.weapon, "name", "Weapon")
        target_name = "" if self.result.target is None else f" vs {getattr(self.result.target, 'name', 'Target')}"
        title = f"{weapon_name} - {selected.name.replace('_', ' ').title()}{target_name}"
        return self._table(("stat", "base", "modded", "effective", "average", "final normal | weakpoint | resistant"), rows, title=title)

    def contributions(self, metric: str = "total_dps") -> str:
        calculator = Calculator(self.result.weapon, self.result.target)
        shapley = shapley_contributions(calculator, self.result.loadout, attack=self.result.selected_attack, metric=metric, state=self.result.state)
        if not shapley: return ""
        removal = removal_contributions(calculator, self.result.loadout, attack=self.result.selected_attack, metric=metric, state=self.result.state)
        rows = [(name, f"{share:.2%}", f"{removal[name]:.2f}") for name, share in shapley.items()]
        return self._table(("component", "shapley", "removal"), rows, title=f"{self.result.weapon.name} - {self.result.selected_attack.replace('_', ' ').title()}")

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
