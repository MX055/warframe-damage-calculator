from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Self

from .effects import ChannelValue, Effect, EffectChannel, EffectMode, Scalar


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

    def __init__(self, **stats: Effect | Iterable[Effect]) -> None:
        effects: dict[str, tuple[Effect, ...]] = {}
        for stat, source in stats.items():
            values = (source,) if isinstance(source, Effect) else tuple(source)
            if not values or not all(isinstance(value, Effect) for value in values): raise TypeError(f"{stat} requires one or more Effect values")
            effects[stat] = values
        self._effects = effects

    def __getitem__(self, stat: str) -> tuple[Effect, ...]:
        return self._effects[stat]

    def __iter__(self) -> Iterator[str]:
        return iter(self._effects)

    def __len__(self) -> int:
        return len(self._effects)

    def __getattr__(self, stat: str) -> tuple[Effect, ...]:
        try: effects = object.__getattribute__(self, "_effects")
        except AttributeError: raise AttributeError(stat) from None
        try: return effects[stat]
        except KeyError: raise AttributeError(stat) from None

    @property
    def manual_fields(self) -> frozenset[str]:
        return frozenset(str(condition) for effects in self.values() for effect in effects if (condition := effect.program.manual_value("when")) is not None)

    def copy(self) -> UpgradeStats:
        return UpgradeStats(**{stat: tuple(deepcopy(effect) for effect in effects) for stat, effects in self.items()})

    @classmethod
    def from_record(cls, record: Mapping[str, list[dict[str, dict[str, ChannelValue]]]]) -> UpgradeStats:
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
    __slots__ = ("name", "kind", "slot", "max_rank", "compatibility", "conflicts", "stats", "combos", "runtime")

    def __init__(self, *, name: str, kind: str = "mod", slot: str = "normal", max_rank: int = 0, compatibility: Compatibility | None = None, conflicts: Iterable[str] = (), stats: UpgradeStats | None = None, combos: Mapping[str, Any] | None = None, runtime: Mapping[str, Any] | None = None) -> None:
        self.name = name
        self.kind = kind
        self.slot = slot
        self.max_rank = int(max_rank)
        self.compatibility = compatibility or Compatibility()
        self.conflicts = list(conflicts)
        self.stats = stats or UpgradeStats()
        self.combos = deepcopy(dict(combos or {}))
        defaults: dict[str, Any] = {"rank": self.max_rank}
        for effects in self.stats.values():
            for effect in effects:
                condition = effect.program.manual_value("when")
                if condition is None: continue
                maximum = effect.program.manual_value("stacks")
                value = int(maximum) if maximum not in (None, "inf") else True
                key = str(condition)
                if isinstance(value, int) and not isinstance(value, bool): defaults[key] = max(int(defaults.get(key, 0)), value)
                else: defaults.setdefault(key, value)
        defaults.update(runtime or {})
        self.runtime = Runtime({"rank", *self.stats.manual_fields}, defaults)

    def set(self, **values: Any) -> Self:
        self.runtime.set(**values)
        return self

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Upgrade:
        allowed = {"name", "kind", "slot", "max_rank", "compatibility", "conflicts", "stats", "combos"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown upgrade fields: {', '.join(sorted(unknown))}")
        return cls(name=str(record["name"]), kind=str(record.get("kind", "mod")), slot=str(record.get("slot", "normal")), max_rank=int(record.get("max_rank", 0)), compatibility=Compatibility.from_record(record.get("compatibility", {})), conflicts=record.get("conflicts", []), stats=UpgradeStats.from_record(record.get("stats", {})), combos=record.get("combos", {}))

    def copy(self) -> Upgrade:
        return Upgrade(name=self.name, kind=self.kind, slot=self.slot, max_rank=self.max_rank, compatibility=deepcopy(self.compatibility), conflicts=self.conflicts, stats=self.stats.copy(), combos=self.combos, runtime=self.runtime.as_dict())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Upgrade) and self.name == other.name and self.kind == other.kind and self.slot == other.slot

    def __hash__(self) -> int:
        return hash((self.name, self.kind, self.slot))

    def resolve_manual(self) -> tuple[ResolvedEffect, ...]:
        rank = min(max(int(self.runtime.rank), 0), self.max_rank)
        rank_scale = 1 if self.max_rank == 0 else (rank + 1) / (self.max_rank + 1)
        resolved: list[ResolvedEffect] = []
        for stat, effects in self.stats.items():
            for effect in effects:
                program = effect.program
                required_rank = program.manual_value("requires_rank")
                if required_rank is not None and rank < int(required_rank): continue
                value = program.value
                if program.scales_with_rank and required_rank is None and isinstance(value, (int, float)) and not isinstance(value, bool): value *= rank_scale
                condition = program.manual_value("when")
                if condition is not None:
                    supplied = getattr(self.runtime, str(condition))
                    if not supplied: continue
                    stacks = 1 if isinstance(supplied, bool) else int(supplied)
                    maximum = program.manual_value("stacks")
                    if maximum not in (None, "inf"): stacks = min(stacks, int(maximum))
                    if isinstance(value, (int, float)) and not isinstance(value, bool): value *= stacks
                resolved.append(ResolvedEffect(self.name, stat, value, program.mode, program.family, program.maximum, program.automatic))
        return tuple(resolved)


class Build:
    __slots__ = ("upgrades",)

    def __init__(self, *upgrades: Upgrade) -> None:
        self.upgrades = [upgrade.copy() for upgrade in upgrades]

    def __iter__(self) -> Iterator[Upgrade]:
        return iter(self.upgrades)

    def __len__(self) -> int:
        return len(self.upgrades)

    def __getitem__(self, index: int) -> Upgrade:
        return self.upgrades[index]

    def __add__(self, other: Upgrade | Build) -> Build:
        additions = other.upgrades if isinstance(other, Build) else [other]
        return Build(*self.upgrades, *additions)

    def __sub__(self, other: Upgrade | Build) -> Build:
        removals = set(other.upgrades if isinstance(other, Build) else [other])
        return Build(*(upgrade for upgrade in self.upgrades if upgrade not in removals))

    def set(self, **values: Any) -> Self:
        consumed: set[str] = set()
        for upgrade in self.upgrades:
            accepted = ({"rank"} | set(upgrade.stats.manual_fields)) & values.keys()
            if accepted:
                upgrade.set(**{key: values[key] for key in accepted})
                consumed.update(accepted)
        unknown = set(values) - consumed
        if unknown: raise TypeError(f"build cannot consume runtime fields: {', '.join(sorted(unknown))}")
        return self

    def copy(self) -> Build:
        return Build(*self.upgrades)
