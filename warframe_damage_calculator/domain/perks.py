from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .effects import Effect, Scalar, Source, resolve_source
from .implementation import ImplementationStatus
from .upgrades import ResolvedEffect, Upgrade, UpgradeStats


class Perk(Upgrade):
    type = "perk"
    __slots__ = ("description",)

    def __init__(self, name: str, description: str = "", stats: UpgradeStats | None = None, implementation_status: ImplementationStatus | None = None) -> None:
        super().__init__(name=name, stats=stats, implementation_status=implementation_status)
        self.description = description

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Perk:
        return cls(name=str(record["name"]), description=str(record.get("description", "")), stats=UpgradeStats.from_record(record.get("stats", {})), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")))


@dataclass(frozen=True, slots=True)
class PerkValues:
    perk: Perk
    tier: int
    choice: int
    values: Mapping[str, tuple[Scalar, ...]] = field(compare=False, hash=False)
    description: str = field(default="", compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType({stat: tuple(values) for stat, values in self.values.items()}))

    def __reduce__(self):
        return type(self), (self.perk, self.tier, self.choice, dict(self.values), self.description)

    @classmethod
    def from_record(cls, perk: Perk, tier: int, choice: int, record: Mapping[str, Any]) -> PerkValues:
        if record.get("perk") != perk.name: raise ValueError(f"perk record does not reference {perk.name}")
        raw_values = record.get("values", {})
        if not isinstance(raw_values, Mapping): raise TypeError(f"{perk.name} values must be a mapping")
        values = {str(stat): tuple(items) if isinstance(items, list) else (items,) for stat, items in raw_values.items()}
        return cls(perk, tier, choice, values, str(record.get("description", "")))


@dataclass(frozen=True, slots=True)
class ResolvedPerk:
    perk: Perk
    tier: int
    choice: int
    effects: tuple[ResolvedEffect, ...]


def resolve_perk(perk_values: PerkValues, *, weapon_name: str, state: Mapping[str, object]) -> ResolvedPerk:
    perk = perk_values.perk
    sources = [effect.value for effects in perk.stats.values() for effect in effects if isinstance(effect.value, Source)]
    referenced = {source.path.removeprefix("$values.").split("[", 1)[0].split(".", 1)[0] for source in sources if source.path.startswith("$values.")}
    if any(not source.path.startswith("$values.") for source in sources): raise ValueError(f"{perk.name} contains a non-value source")
    missing = referenced - set(perk_values.values)
    unknown = set(perk_values.values) - referenced
    if missing: raise ValueError(f"{weapon_name} supplies no values for {perk.name}: {', '.join(sorted(missing))}")
    if unknown: raise ValueError(f"{weapon_name} supplies unknown values for {perk.name}: {', '.join(sorted(unknown))}")
    resolved: list[ResolvedEffect] = []
    for stat, templates in perk.stats.items():
        for template in templates:
            if not isinstance(template.value, Source): raise ValueError(f"{perk.name}.{stat} is not a source template")
            value = resolve_source(template.value, {"values": perk_values.values})
            if template.when is not None:
                supplied = state.get(template.when, False)
                if not supplied: continue
                stacks = 1 if isinstance(supplied, bool) else int(supplied)
                if template.stacks not in (None, "inf"): stacks = min(stacks, int(template.stacks))
                if isinstance(value, (int, float)) and not isinstance(value, bool): value *= stacks
            resolved.append(ResolvedEffect(perk.name, stat, value, template.mode, template.family, template.maximum, deepcopy(template.automatic)))
    return ResolvedPerk(perk, perk_values.tier, perk_values.choice, tuple(resolved))
