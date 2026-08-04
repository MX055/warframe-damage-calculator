from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self

from .effects import Effect, Scalar, Source, resolve_automatic, resolve_source
from .implementation import ImplementationStatus
from .runtime import Runtime
from .upgrades import ResolvedEffect, Upgrade, UpgradeStats, _merge_runtime, _runtime_defaults

PERK_DESCRIPTION_SOURCE = Source("$description")

# Explicit slot names when effect metadata alone is not distinctive enough.
PERK_VALUE_KEY_OVERRIDES: dict[tuple[str, str], tuple[str, ...]] = {
    ("Thane's Wrath", "damage"): ("base", "armor_over_450"),
}


def _effect_record(effect: Effect | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(effect, Mapping):
        return effect
    return {
        "mode": effect.mode,
        "when": effect.when,
        "stacks": effect.stacks,
        "automatic": dict(effect.automatic or {}),
    }


def _primary_value_key(effect: Mapping[str, Any]) -> str:
    automatic = effect.get("automatic") if isinstance(effect.get("automatic"), Mapping) else {}
    when = effect.get("when")
    auto_when = automatic.get("when") if isinstance(automatic, Mapping) else None
    mode = effect.get("mode")
    if when:
        return str(when)
    if auto_when:
        return str(auto_when)
    if mode in {"base", "flat"}:
        return str(mode)
    return "base"


def perk_value_keys(perk_name: str, stat: str, effects: Sequence[Effect | Mapping[str, Any]]) -> tuple[str, ...]:
    """Stable, explicit names for each `$values.<stat>.<key>` slot on a perk template."""
    override = PERK_VALUE_KEY_OVERRIDES.get((perk_name, stat))
    if override is not None:
        if len(override) != len(effects):
            raise ValueError(f"{perk_name}.{stat}: override length {len(override)} != {len(effects)} effects")
        return override

    records = [_effect_record(effect) for effect in effects]
    primaries = [_primary_value_key(record) for record in records]
    counts = Counter(primaries)
    used: set[str] = set()
    keys: list[str] = []
    for primary, record in zip(primaries, records, strict=True):
        key = primary
        if counts[primary] > 1:
            automatic = record.get("automatic") if isinstance(record.get("automatic"), Mapping) else {}
            stacks = record.get("stacks")
            auto_when = automatic.get("when") if isinstance(automatic, Mapping) else None
            mode = record.get("mode")
            if stacks is not None and stacks != "inf":
                key = f"{primary}_stacks_{int(stacks)}"
            elif auto_when and str(auto_when) not in key:
                key = f"{key}_{auto_when}"
            elif mode in {"base", "flat"} and str(mode) not in key:
                key = f"{key}_{mode}"
        base = key
        suffix = 2
        while key in used:
            key = f"{base}_{suffix}"
            suffix += 1
        used.add(key)
        keys.append(key)
    return tuple(keys)


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple((key, _freeze_json(item)) for key, item in sorted(value.items()))
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def effect_signature(effect: Effect | Mapping[str, Any]) -> tuple[object, ...]:
    """Metadata identity used to match weapon evolution stats to perk template slots."""
    record = _effect_record(effect)
    automatic = record.get("automatic") if isinstance(record.get("automatic"), Mapping) else {}
    mode = record.get("mode") or "proportional"
    return (str(mode), record.get("when"), record.get("stacks"), _freeze_json(dict(automatic or {})))


def concrete_effect_record(template: Mapping[str, Any], value: Scalar) -> dict[str, Any]:
    """Build an upgrade-style effect entry from a perk template slot and concrete value."""
    record = {key: deepcopy(item) for key, item in template.items() if key != "value"}
    record["value"] = value
    record.setdefault("automatic", {})
    return record


def values_from_evolution_stats(perk: Perk, stats: Mapping[str, Any]) -> dict[str, dict[str, Scalar]]:
    """Map upgrade-style evolution stats onto named `$values` slots."""
    if not isinstance(stats, Mapping):
        raise TypeError(f"{perk.name} stats must be a mapping")
    unknown = set(stats) - set(perk.stats)
    if unknown:
        raise ValueError(f"{perk.name} has unknown stats: {', '.join(sorted(unknown))}")
    values: dict[str, dict[str, Scalar]] = {}
    for stat, templates in perk.stats.items():
        keys = perk_value_keys(perk.name, stat, templates)
        raw_effects = stats.get(stat, ())
        if not isinstance(raw_effects, (list, tuple)):
            raise TypeError(f"{perk.name} stats.{stat} must be a list of effects")
        remaining = [dict(effect) for effect in raw_effects]
        named: dict[str, Scalar] = {}
        for template, key in zip(templates, keys, strict=True):
            signature = effect_signature(template)
            match = next((index for index, effect in enumerate(remaining) if effect_signature(effect) == signature), None)
            if match is None:
                continue
            effect = remaining.pop(match)
            value = effect.get("value")
            if not isinstance(value, (int, float, bool, str)) or isinstance(value, str) and not value:
                raise TypeError(f"{perk.name} stats.{stat} has an invalid concrete value")
            if value != 0 and value != 0.0:
                named[key] = value
        if remaining:
            raise ValueError(f"{perk.name}.{stat}: unmatched evolution effects")
        if named:
            values[stat] = named
    return values


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

    def value_keys(self, stat: str) -> tuple[str, ...]:
        return perk_value_keys(self.name, stat, self.stats.get(stat, ()))


@dataclass(frozen=True, slots=True)
class PerkValues:
    perk: Perk
    tier: int
    choice: int
    values: Mapping[str, Mapping[str, Scalar]] = field(compare=False, hash=False)
    description: str = field(default="", compare=False, hash=False)

    def __post_init__(self) -> None:
        normalized: dict[str, Mapping[str, Scalar]] = {}
        for stat, slots in self.values.items():
            if not isinstance(slots, Mapping):
                raise TypeError(f"{self.perk.name} values.{stat} must be a mapping of named slots")
            normalized[str(stat)] = MappingProxyType({str(key): value for key, value in slots.items()})
        object.__setattr__(self, "values", MappingProxyType(normalized))

    def __reduce__(self):
        return type(self), (self.perk, self.tier, self.choice, {stat: dict(slots) for stat, slots in self.values.items()}, self.description)

    @classmethod
    def from_record(cls, perk: Perk, tier: int, choice: int, record: Mapping[str, Any]) -> PerkValues:
        if record.get("perk") != perk.name: raise ValueError(f"perk record does not reference {perk.name}")
        if "values" in record:
            raise ValueError(f"{perk.name}: evolution field 'values' was renamed to 'stats'")
        raw_stats = record.get("stats", {})
        values = values_from_evolution_stats(perk, raw_stats)
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
    if any(not isinstance(source, Source) or not source.path.startswith("$values.") for source in sources):
        raise ValueError(f"{active.name} contains a non-value source")
    referenced = {source.path.removeprefix("$values.").split(".", 1)[0] for source in sources}
    unknown = set(perk_values.values) - referenced
    if unknown:
        raise ValueError(f"{weapon_name} supplies unknown values for {active.name}: {', '.join(sorted(unknown))}")
    for stat, slots in perk_values.values.items():
        allowed = set(active.value_keys(stat))
        invalid = set(slots) - allowed
        if invalid:
            raise ValueError(f"{weapon_name} supplies unknown {active.name}.{stat} value keys: {', '.join(sorted(invalid))}")
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
