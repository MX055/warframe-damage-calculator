from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self

from .effects import Effect, Scalar, Source, resolve_automatic, resolve_source
from .implementation import ImplementationStatus
from .runtime import Runtime
from .upgrades import ResolvedEffect, Upgrade, UpgradeStats, _merge_runtime, _runtime_defaults

PERK_DESCRIPTION_SOURCE = Source("$description")


class Perk(Upgrade):
    type = "perk"
    __slots__ = ("description_source", "runtime")

    def __init__(self, *, name: str, description: str | Source | None = None, stats: UpgradeStats | None = None, implementation_status: ImplementationStatus | None = None, runtime: Runtime | None = None) -> None:
        super().__init__(name=name, description=None, stats=stats, implementation_status=implementation_status)
        self.description_source = self._parse_description(description)
        defaults = _runtime_defaults(self.stats, base={})
        self.runtime = _merge_runtime({*self.stats.manual_fields}, defaults, runtime)

    @staticmethod
    def _parse_description(value: str | Source | None) -> Source:
        if value is None or value == "": return PERK_DESCRIPTION_SOURCE
        if isinstance(value, Source):
            if value.path != "$description": raise ValueError("perk description source must be '$description'")
            return value
        raise TypeError("perk description must be a $description source expression")

    def set(self, **values: Any) -> Self:
        self.runtime.set(**values)
        return self

    def copy(self) -> Self:
        return type(self)(name=self.name, description=self.description_source, stats=self.stats.copy(), implementation_status=deepcopy(self.implementation_status), runtime=self.runtime.copy())

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Perk:
        raw = record.get("description")
        if isinstance(raw, Mapping): description: str | Source | None = Source.from_record(raw)
        elif raw is None or isinstance(raw, str): description = raw
        else: raise TypeError("perk description must be a string, source expression, or null")
        return cls(name=str(record["name"]), description=description, stats=UpgradeStats.from_record(record.get("stats", {})), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")))


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
    description: str
    effects: tuple[ResolvedEffect, ...]


def resolve_perk(perk_values: PerkValues, *, weapon_name: str, perk: Perk | None = None) -> ResolvedPerk:
    active = perk or perk_values.perk
    sources = [effect.value for effects in active.stats.values() for effect in effects if isinstance(effect.value, Source)]
    referenced = {source.path.removeprefix("$values.").split("[", 1)[0].split(".", 1)[0] for source in sources if source.path.startswith("$values.")}
    if any(not source.path.startswith("$values.") for source in sources): raise ValueError(f"{active.name} contains a non-value source")
    missing = referenced - set(perk_values.values)
    unknown = set(perk_values.values) - referenced
    if missing: raise ValueError(f"{weapon_name} supplies no values for {active.name}: {', '.join(sorted(missing))}")
    if unknown: raise ValueError(f"{weapon_name} supplies unknown values for {active.name}: {', '.join(sorted(unknown))}")
    description = str(resolve_source(active.description_source, {"description": perk_values.description}))
    resolved: list[ResolvedEffect] = []
    for stat, templates in active.stats.items():
        for template in templates:
            if not isinstance(template.value, Source): raise ValueError(f"{active.name}.{stat} is not a source template")
            value = resolve_source(template.value, {"values": perk_values.values})
            if template.when is not None:
                supplied = getattr(active.runtime, template.when)
                if not supplied: continue
                stacks = 1 if isinstance(supplied, bool) else int(supplied)
                if template.stacks not in (None, "inf"): stacks = min(stacks, int(template.stacks))
                if isinstance(value, (int, float)) and not isinstance(value, bool): value *= stacks
            resolved.append(ResolvedEffect(active.name, stat, value, template.mode, template.family, template.maximum, resolve_automatic(template.automatic, 0, 0)))
    return ResolvedPerk(active, perk_values.tier, perk_values.choice, description, tuple(resolved))
