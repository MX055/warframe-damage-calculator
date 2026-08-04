from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Self

from .effects import Source, resolve_automatic, resolve_source
from .implementation import ImplementationStatus
from .runtime import Runtime
from .scaled_values import UpgradeValue, resolve_scalar
from .upgrades import ResolvedEffect, Upgrade, UpgradeStats, _merge_runtime, _runtime_defaults

PERK_DESCRIPTION_SOURCE = Source("$description")
PERK_STATS_MARKER = "$stats"
PERK_DESCRIPTION_MARKER = "$description"


class Perk(Upgrade):
    type = "perk"
    default_slot_type = "perk"
    __slots__ = ("slot_type", "description_source", "runtime")

    def __init__(self, *, name: str, description: str | Source | None = None, slot_type: str | None = None, stats: str | None = None, implementation_status: ImplementationStatus | None = None, runtime: Runtime | None = None) -> None:
        if stats is not None and stats != PERK_STATS_MARKER:
            raise TypeError("perk stats must be '$stats'")
        super().__init__(name=name, description=None, stats=UpgradeStats(), implementation_status=implementation_status)
        self.slot_type = slot_type or self.default_slot_type
        self.description_source = self._parse_description(description)
        overrides = runtime.as_dict() if runtime is not None else {}
        self.runtime = Runtime(set(overrides), overrides)

    @staticmethod
    def _parse_description(value: str | Source | None) -> Source:
        if value is None or value == "" or value == PERK_DESCRIPTION_MARKER:
            return PERK_DESCRIPTION_SOURCE
        if isinstance(value, Source):
            if value.path != "$description":
                raise ValueError("perk description source must be '$description'")
            return value
        raise TypeError("perk description must be '$description'")

    def set(self, **values: Any) -> Self:
        allowed = set(self.runtime.as_dict()) | set(values)
        merged = {**self.runtime.as_dict(), **values}
        self.runtime = Runtime(allowed, merged)
        return self

    def copy(self) -> Self:
        return type(self)(name=self.name, description=self.description_source, slot_type=self.slot_type, stats=PERK_STATS_MARKER, implementation_status=deepcopy(self.implementation_status), runtime=self.runtime.copy())

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Perk:
        raw = record.get("description")
        if isinstance(raw, Mapping):
            description: str | Source | None = Source.from_record(raw)
        elif raw is None or isinstance(raw, str):
            description = raw
        else:
            raise TypeError("perk description must be '$description'")
        stats = record.get("stats", PERK_STATS_MARKER)
        if stats != PERK_STATS_MARKER:
            raise TypeError("perk stats must be '$stats'")
        return cls(name=str(record["name"]), description=description, slot_type=record.get("slot_type"), stats=PERK_STATS_MARKER, implementation_status=ImplementationStatus.from_record(record.get("implementation_status")))


@dataclass(frozen=True, slots=True)
class PerkValues:
    perk: Perk
    tier: int
    stats: UpgradeStats = field(compare=False, hash=False)
    description: str = field(default="", compare=False, hash=False)

    def __post_init__(self) -> None:
        stats = self.stats
        if isinstance(stats, Mapping) and not isinstance(stats, UpgradeStats):
            stats = UpgradeStats.from_record(stats)
        elif not isinstance(stats, UpgradeStats):
            raise TypeError(f"{self.perk.name} stats must be UpgradeStats")
        object.__setattr__(self, "stats", stats)

    def __reduce__(self):
        return type(self), (self.perk, self.tier, self.stats.copy(), self.description)

    @classmethod
    def from_record(cls, perk: Perk, tier: int, record: Mapping[str, Any]) -> PerkValues:
        if "perk" in record:
            raise ValueError(f"{perk.name}: perk name is the evolution key; remove 'perk' field")
        if "values" in record:
            raise ValueError(f"{perk.name}: evolution field 'values' was renamed to 'stats'")
        raw_stats = record.get("stats", {})
        if not isinstance(raw_stats, Mapping):
            raise TypeError(f"{perk.name} stats must be a mapping")
        return cls(perk, tier, UpgradeStats.from_record(raw_stats), str(record.get("description", "")))


@dataclass(frozen=True, slots=True)
class ResolvedPerk:
    perk: Perk
    tier: int
    description: str
    effects: tuple[ResolvedEffect, ...]


def resolve_perk(perk_values: PerkValues, *, weapon_name: str, perk: Perk | None = None) -> ResolvedPerk:
    active = perk or perk_values.perk
    defaults = _runtime_defaults(perk_values.stats, base={})
    overrides = active.runtime.as_dict()
    runtime = _merge_runtime(set(defaults) | set(overrides), defaults, Runtime(set(overrides), overrides) if overrides else None)
    description = str(resolve_source(active.description_source, {"description": perk_values.description}))
    resolved: list[ResolvedEffect] = []
    for stat, effects in perk_values.stats.items():
        for effect in effects:
            if isinstance(effect.value, Source):
                raise ValueError(f"{weapon_name} supplies a source value for {active.name}.{stat}; expected a concrete value")
            value = resolve_scalar(effect.value, 0, 0, mode=effect.mode) if isinstance(effect.value, UpgradeValue) else effect.value
            if effect.when is not None:
                supplied = getattr(runtime, effect.when, False)
                if not supplied:
                    continue
                stacks = 1 if isinstance(supplied, bool) else int(supplied)
                if effect.stacks not in (None, "inf"):
                    stacks = min(stacks, int(effect.stacks))
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    value *= stacks
            resolved.append(ResolvedEffect(active.name, stat, value, effect.mode, effect.family, effect.maximum, resolve_automatic(effect.automatic, 0, 0)))
    return ResolvedPerk(active, perk_values.tier, description, tuple(resolved))
