from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar, Self

from .attacks import Attack
from .effect_stats import MULTIPLICATIVE_EFFECT_STATS
from .effects import Automatic, Effect, EffectChannel, EffectMode, EffectValue, Source, resolve_automatic
from .generated_attacks import GENERATED_ATTACK_STAT, resolve_generated_payload
from .implementation import ImplementationStatus
from .runtime import Runtime
from .scaled_values import UpgradeValue, resolve_scalar


COMBO_TYPES = frozenset({"aerial", "block", "finisher", "forward", "forward_block", "heavy", "neutral", "slam", "slide", "wall"})
COMBO_FIELDS = frozenset({"type", "name", "multiplier", "hits", "duration"})


@dataclass(slots=True)
class Combo:
    type: str
    name: str
    multiplier: float
    hits: float
    duration: float

    def __post_init__(self) -> None:
        self.type = str(self.type)
        self.name = str(self.name)
        if self.type not in COMBO_TYPES: raise ValueError(f"unsupported combo type {self.type!r}")
        if not self.name: raise ValueError("combo name is required")
        self.multiplier = float(self.multiplier)
        self.hits = float(self.hits)
        self.duration = float(self.duration)

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Combo:
        if not isinstance(record, Mapping) or set(record) - COMBO_FIELDS or not COMBO_FIELDS <= set(record): raise ValueError("combo requires type, name, multiplier, hits, and duration")
        return cls(str(record["type"]), str(record["name"]), float(record["multiplier"]), float(record["hits"]), float(record["duration"]))  # type: ignore[arg-type]

    def to_record(self) -> dict[str, object]:
        return {"type": self.type, "name": self.name, "multiplier": self.multiplier, "hits": self.hits, "duration": self.duration}


def _parse_combos(combos: Mapping[str, Combo | Mapping[str, object]] | None) -> dict[str, Combo]:
    if combos is None: return {}
    if not isinstance(combos, Mapping): raise TypeError("combos must be a mapping of id to Combo")
    parsed: dict[str, Combo] = {}
    for combo_id, value in combos.items():
        if not isinstance(combo_id, str) or not combo_id or any(ch == " " for ch in combo_id): raise ValueError("combo ids must be nonempty identifiers")
        parsed[combo_id] = value if isinstance(value, Combo) else Combo.from_record(value)
    return parsed


class UpgradeStats(Mapping[str, tuple[Effect, ...]]):
    __slots__ = ("_effects",)

    def __init__(self, **stats: Effect | EffectValue | Attack | Iterable[Effect | EffectValue | Attack]) -> None:
        effects: dict[str, tuple[Effect, ...]] = {}
        for stat, source in stats.items():
            if stat == GENERATED_ATTACK_STAT:
                values = (source,) if isinstance(source, (Effect, Attack, Mapping)) and not isinstance(source, (str, bytes)) else tuple(source)
                if not values: raise TypeError(f"{stat} requires one or more effect values")
                parsed: list[Effect] = []
                for value in values:
                    if isinstance(value, Effect): parsed.append(value)
                    elif isinstance(value, Attack):
                        effect = Effect(value.to_generated_value(), rank_scale=None)
                        effect.automatic = (value.automatic or Automatic()).to_channel()
                        parsed.append(effect)
                    else:
                        attack = Attack.from_record(value)
                        effect = Effect(attack.to_generated_value(), rank_scale=None)
                        effect.automatic = (attack.automatic or Automatic()).to_channel()
                        parsed.append(effect)
                effects[stat] = tuple(parsed)
                continue
            values = (source,) if isinstance(source, (Effect, int, float, bool, str, Mapping, UpgradeValue)) else tuple(source)
            if not values: raise TypeError(f"{stat} requires one or more effect values")
            effects[stat] = tuple(value if isinstance(value, Effect) else Effect(value) for value in values)
            if stat not in MULTIPLICATIVE_EFFECT_STATS and any(effect.mode == "multiplicative" for effect in effects[stat]): raise ValueError(f"{stat} does not support multiplicative effects")
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
        parsed: dict[str, tuple[Effect, ...]] = {}
        for stat, effects in record.items():
            if stat == GENERATED_ATTACK_STAT:
                items: list[Effect] = []
                for effect in effects:
                    attack = Attack.from_record(effect)
                    item = Effect(attack.to_generated_value(), rank_scale=None)
                    item.automatic = (attack.automatic or Automatic()).to_channel()
                    items.append(item)
                parsed[stat] = tuple(items)
            else:
                parsed[stat] = tuple(Effect.from_record(effect) for effect in effects)
        return cls(**parsed)

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
        if "aoe" in record and not isinstance(record["aoe"], bool): raise TypeError("compatibility aoe must be a bool")
        return cls(list(record.get("types", [])), list(record.get("subtypes", [])), list(record.get("names", [])), list(record.get("categories", [])), list(record.get("triggers", [])), record.get("aoe"))


@dataclass(frozen=True, slots=True)
class ResolvedEffect:
    source: str
    stat: str
    value: EffectValue
    mode: EffectMode
    family: str
    maximum: float | None
    automatic: EffectChannel


class Upgrade:
    type: ClassVar[str] = "upgrade"
    __slots__ = ("name", "description", "implementation_status", "stats")

    def __init__(self, *, name: str, description: str = "", implementation_status: ImplementationStatus | None = None, stats: UpgradeStats | None = None) -> None:
        self.name = name
        self.description = description
        self.implementation_status = implementation_status or ImplementationStatus()
        self.stats = stats or UpgradeStats()

    @property
    def implemented(self) -> bool: return self.implementation_status.implemented

    def __eq__(self, other: object) -> bool: return type(self) is type(other) and isinstance(other, Upgrade) and self.name == other.name
    def __hash__(self) -> int: return hash((type(self), self.name))


class _RankedUpgrade(Upgrade):
    default_slot: ClassVar[str]
    __slots__ = ("slot", "max_rank", "compatibility", "conflicts", "combos", "runtime")

    def __init__(self, *, name: str, description: str = "", slot: str | None = None, max_rank: int = 0, implementation_status: ImplementationStatus | None = None, compatibility: Compatibility | None = None, conflicts: Iterable[str] = (), stats: UpgradeStats | None = None, combos: Mapping[str, Combo | Mapping[str, object]] | None = None, runtime: Mapping[str, Any] | None = None) -> None:
        super().__init__(name=name, description=description, implementation_status=implementation_status, stats=stats)
        self.slot = slot or self.default_slot
        self.max_rank = int(max_rank)
        self.compatibility = compatibility or Compatibility()
        self.conflicts = list(conflicts)
        self.combos = _parse_combos(combos)
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
        allowed = {"name", "description", "slot", "max_rank", "implementation_status", "compatibility", "conflicts", "stats", "combos"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown {cls.type} fields: {', '.join(sorted(unknown))}")
        return cls(name=str(record["name"]), description=str(record.get("description", "")), slot=record.get("slot"), max_rank=int(record.get("max_rank", 0)), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")), compatibility=Compatibility.from_record(record.get("compatibility", {})), conflicts=record.get("conflicts", []), stats=UpgradeStats.from_record(record.get("stats", {})), combos=record.get("combos", {}))

    def copy(self) -> Self:
        return type(self)(name=self.name, description=self.description, slot=self.slot, max_rank=self.max_rank, implementation_status=self.implementation_status, compatibility=deepcopy(self.compatibility), conflicts=self.conflicts, stats=self.stats.copy(), combos={combo_id: Combo(**combo.to_record()) for combo_id, combo in self.combos.items()}, runtime=self.runtime.as_dict())

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and isinstance(other, _RankedUpgrade) and self.name == other.name and self.slot == other.slot

    def __hash__(self) -> int: return hash((type(self), self.name, self.slot))

    def resolve_manual(self) -> tuple[ResolvedEffect, ...]:
        rank = min(max(int(self.runtime.rank), 0), self.max_rank)
        resolved: list[ResolvedEffect] = []
        for stat, effects in self.stats.items():
            for effect in effects:
                if effect.requires_rank is not None and rank < effect.requires_rank: continue
                if stat == GENERATED_ATTACK_STAT:
                    if not isinstance(effect.value, Mapping): raise TypeError("generated_attack value must be an object")
                    payload = resolve_generated_payload(effect.value, rank, self.max_rank)
                    automatic = resolve_automatic(effect.automatic, rank, self.max_rank)
                    resolved.append(ResolvedEffect(self.name, stat, payload, effect.mode, effect.family, effect.maximum, automatic))
                    continue
                value: object = effect.value
                if isinstance(value, UpgradeValue): value = resolve_scalar(value, rank, self.max_rank, mode=effect.mode)
                elif isinstance(value, Source) and isinstance(value.multiplier, UpgradeValue):
                    value = Source(value.path, resolve_scalar(value.multiplier, rank, self.max_rank), value.default)
                if effect.when is not None:
                    supplied = getattr(self.runtime, effect.when)
                    if not supplied: continue
                    stacks = 1 if isinstance(supplied, bool) else int(supplied)
                    if effect.stacks not in (None, "inf"): stacks = min(stacks, int(effect.stacks))
                    if isinstance(value, (int, float)) and not isinstance(value, bool): value = value ** stacks if effect.mode == "multiplicative" else value * stacks
                automatic = resolve_automatic(effect.automatic, rank, self.max_rank)
                resolved.append(ResolvedEffect(self.name, stat, value, effect.mode, effect.family, effect.maximum, automatic))
        return tuple(resolved)

class Mod(_RankedUpgrade):
    type = "mod"
    default_slot = "regular_mod"


class Arcane(_RankedUpgrade):
    type = "arcane"
    default_slot = "regular_arcane"
