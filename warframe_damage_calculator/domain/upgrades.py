from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Self

from .effects import PLACEHOLDER, Effect, EffectChannel, EffectMode, Placeholder, Scalar
from .implementation import ImplementationStatus


class Runtime:
    __slots__ = ("_allowed", "_values")

    def __init__(self, allowed: Iterable[str], values: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_allowed", frozenset(allowed))
        unknown = set(values) - self._allowed
        if unknown: raise TypeError(f"unknown runtime fields: {', '.join(sorted(unknown))}")
        object.__setattr__(self, "_values", dict(values))

    def __getattr__(self, name: str) -> Any:
        try: return self._values[name]
        except KeyError: raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in self._allowed: raise TypeError(f"unknown runtime field {name!r}")
        self._values[name] = value

    def set(self, **values: Any) -> None:
        unknown = set(values) - self._allowed
        if unknown: raise TypeError(f"unknown runtime fields: {', '.join(sorted(unknown))}")
        self._values.update(values)

    def copy(self) -> Runtime:
        return Runtime(self._allowed, deepcopy(self._values))

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._values)


class UpgradeStats(Mapping[str, tuple[Effect, ...]]):
    __slots__ = ("_effects",)

    def __init__(self, **stats: Effect | Scalar | Iterable[Effect | Scalar]) -> None:
        effects: dict[str, tuple[Effect, ...]] = {}
        for stat, source in stats.items():
            values = (source,) if isinstance(source, (Effect, int, float, bool, str)) else tuple(source)
            if not values: raise TypeError(f"{stat} requires one or more effect values")
            effects[stat] = tuple(value if isinstance(value, Effect) else Effect(value) for value in values)
        self._effects = effects

    def __getitem__(self, stat: str) -> tuple[Effect, ...]: return self._effects[stat]
    def __iter__(self) -> Iterator[str]: return iter(self._effects)
    def __len__(self) -> int: return len(self._effects)

    def __getattr__(self, stat: str) -> tuple[Effect, ...]:
        try: effects = object.__getattribute__(self, "_effects")
        except AttributeError: raise AttributeError(stat) from None
        try: return effects[stat]
        except KeyError: raise AttributeError(stat) from None

    @property
    def manual_fields(self) -> frozenset[str]:
        return frozenset(effect.when for effects in self.values() for effect in effects if effect.when is not None)

    def copy(self) -> UpgradeStats:
        return UpgradeStats(**{stat: tuple(deepcopy(effect) for effect in effects) for stat, effects in self.items()})

    @classmethod
    def from_record(cls, record: Mapping[str, list[Mapping[str, object]]]) -> UpgradeStats:
        return cls(**{stat: tuple(Effect.from_record(effect) for effect in effects) for stat, effects in record.items()})


@dataclass(slots=True)
class Compatibility:
    types: list[str] = field(default_factory=list)
    subtypes: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    aoe: bool | None = None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Compatibility:
        allowed = {"types", "subtypes", "names", "categories", "triggers", "aoe"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown compatibility fields: {', '.join(sorted(unknown))}")
        return cls(list(record.get("types", [])), list(record.get("subtypes", [])), list(record.get("names", [])), list(record.get("categories", [])), list(record.get("triggers", [])), record.get("aoe"))


@dataclass(frozen=True, slots=True)
class ResolvedEffect:
    source: str
    stat: str
    value: Scalar
    mode: EffectMode
    family: str
    maximum: float | None
    automatic: EffectChannel


class Upgrade:
    type: ClassVar[str] = "upgrade"
    __slots__ = ("name", "implementation_status", "stats")

    def __init__(self, *, name: str, implementation_status: ImplementationStatus | None = None, stats: UpgradeStats | None = None) -> None:
        self.name = name
        self.implementation_status = implementation_status or ImplementationStatus()
        self.stats = stats or UpgradeStats()

    @property
    def implemented(self) -> bool: return self.implementation_status.implemented

    def __eq__(self, other: object) -> bool: return type(self) is type(other) and isinstance(other, Upgrade) and self.name == other.name
    def __hash__(self) -> int: return hash((type(self), self.name))


class _RankedUpgrade(Upgrade):
    default_slot: ClassVar[str]
    __slots__ = ("slot", "max_rank", "compatibility", "conflicts", "combos", "runtime")

    def __init__(self, *, name: str, slot: str | None = None, max_rank: int = 0, implementation_status: ImplementationStatus | None = None, compatibility: Compatibility | None = None, conflicts: Iterable[str] = (), stats: UpgradeStats | None = None, combos: Mapping[str, Any] | None = None, runtime: Mapping[str, Any] | None = None) -> None:
        super().__init__(name=name, implementation_status=implementation_status, stats=stats)
        self.slot = slot or self.default_slot
        self.max_rank = int(max_rank)
        self.compatibility = compatibility or Compatibility()
        self.conflicts = list(conflicts)
        self.combos = deepcopy(dict(combos or {}))
        defaults: dict[str, Any] = {"rank": self.max_rank}
        for effects in self.stats.values():
            for effect in effects:
                if effect.when is None: continue
                maximum = effect.stacks
                value = int(maximum) if maximum not in (None, "inf") else True
                key = str(effect.when)
                if isinstance(value, int) and not isinstance(value, bool): defaults[key] = max(int(defaults.get(key, 0)), value)
                else: defaults.setdefault(key, value)
        defaults.update(runtime or {})
        self.runtime = Runtime({"rank", *self.stats.manual_fields}, defaults)

    def set(self, **values: Any) -> Self:
        self.runtime.set(**values)
        return self

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        allowed = {"name", "slot", "max_rank", "implementation_status", "compatibility", "conflicts", "stats", "combos"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown {cls.type} fields: {', '.join(sorted(unknown))}")
        return cls(name=str(record["name"]), slot=record.get("slot"), max_rank=int(record.get("max_rank", 0)), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")), compatibility=Compatibility.from_record(record.get("compatibility", {})), conflicts=record.get("conflicts", []), stats=UpgradeStats.from_record(record.get("stats", {})), combos=record.get("combos", {}))

    def copy(self) -> Self:
        return type(self)(name=self.name, slot=self.slot, max_rank=self.max_rank, implementation_status=self.implementation_status, compatibility=deepcopy(self.compatibility), conflicts=self.conflicts, stats=self.stats.copy(), combos=self.combos, runtime=self.runtime.as_dict())

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and isinstance(other, _RankedUpgrade) and self.name == other.name and self.slot == other.slot

    def __hash__(self) -> int: return hash((type(self), self.name, self.slot))

    def resolve_manual(self) -> tuple[ResolvedEffect, ...]:
        rank = min(max(int(self.runtime.rank), 0), self.max_rank)
        rank_scale = 1 if self.max_rank == 0 else (rank + 1) / (self.max_rank + 1)
        resolved: list[ResolvedEffect] = []
        for stat, effects in self.stats.items():
            for effect in effects:
                if effect.requires_rank is not None and rank < effect.requires_rank: continue
                value = effect.value
                if effect.scales_with_rank and effect.requires_rank is None and isinstance(value, (int, float)) and not isinstance(value, bool): value *= rank_scale
                if effect.when is not None:
                    supplied = getattr(self.runtime, effect.when)
                    if not supplied: continue
                    stacks = 1 if isinstance(supplied, bool) else int(supplied)
                    if effect.stacks not in (None, "inf"): stacks = min(stacks, int(effect.stacks))
                    if isinstance(value, (int, float)) and not isinstance(value, bool): value *= stacks
                resolved.append(ResolvedEffect(self.name, stat, value, effect.mode, effect.family, effect.maximum, deepcopy(effect.automatic)))
        return tuple(resolved)


class Mod(_RankedUpgrade):
    type = "mod"
    default_slot = "regular_mod"


class Arcane(_RankedUpgrade):
    type = "arcane"
    default_slot = "regular_arcane"


def placeholder_stats(record: Mapping[str, list[Mapping[str, Any]]]) -> UpgradeStats:
    stats: dict[str, tuple[Effect, ...]] = {}
    for stat, records in record.items():
        effects: list[Effect] = []
        for source in records:
            if source.get("value") != "$weapon": raise ValueError(f"perk placeholder {stat!r} must use '$weapon'")
            template = deepcopy(dict(source))
            template["value"] = PLACEHOLDER
            effects.append(Effect.from_record(template))
        stats[stat] = tuple(effects)
    return UpgradeStats(**stats)


class Perk(Upgrade):
    type = "perk"
    __slots__ = ("description",)

    def __init__(self, name: str, description: str = "", stats: UpgradeStats | None = None, implementation_status: ImplementationStatus | None = None) -> None:
        super().__init__(name=name, stats=stats, implementation_status=implementation_status)
        self.description = description

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Perk:
        return cls(name=str(record["name"]), description=str(record.get("description", "")), stats=placeholder_stats(record.get("stats", {})), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")))


@dataclass(frozen=True, slots=True)
class PerkValues:
    perk: Perk
    tier: int
    choice: int
    values: Mapping[str, tuple[Scalar, ...]] = field(compare=False, hash=False)
    description: str = field(default="", compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType({stat: tuple(values) for stat, values in self.values.items()}))

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
    missing = set(perk.stats) - set(perk_values.values)
    unknown = set(perk_values.values) - set(perk.stats)
    if missing: raise ValueError(f"{weapon_name} supplies no values for {perk.name}: {', '.join(sorted(missing))}")
    if unknown: raise ValueError(f"{weapon_name} supplies unknown values for {perk.name}: {', '.join(sorted(unknown))}")
    resolved: list[ResolvedEffect] = []
    for stat, templates in perk.stats.items():
        values = perk_values.values[stat]
        if len(values) != len(templates): raise ValueError(f"{weapon_name} supplies {len(values)} values for {perk.name}.{stat}; expected {len(templates)}")
        for template, value in zip(templates, values, strict=True):
            if template.value is not PLACEHOLDER: raise ValueError(f"{perk.name}.{stat} is not a placeholder template")
            if value is PLACEHOLDER: raise ValueError(f"{weapon_name} leaves {perk.name}.{stat} unresolved")
            if template.when is not None:
                supplied = state.get(template.when, False)
                if not supplied: continue
                stacks = 1 if isinstance(supplied, bool) else int(supplied)
                if template.stacks not in (None, "inf"): stacks = min(stacks, int(template.stacks))
                if isinstance(value, (int, float)) and not isinstance(value, bool): value *= stacks
            resolved.append(ResolvedEffect(perk.name, stat, value, template.mode, template.family, template.maximum, deepcopy(template.automatic)))
    return ResolvedPerk(perk, perk_values.tier, perk_values.choice, tuple(resolved))
