from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal, Mapping


type Scalar = int | float | bool | str
type ChannelValue = Scalar | list[Scalar]
type EffectChannel = dict[str, ChannelValue]
type EffectMode = Literal["proportional", "base", "flat"]

PROPERTY_FIELDS = frozenset({"value", "mode", "family", "max", "rank_scale"})
MANUAL_FIELDS = frozenset({"when", "stacks", "for", "requires_rank"})
AUTOMATIC_FIELDS = frozenset({"when", "on", "with", "stacks", "for", "chance", "multiply", "reset", "equipped", "per"})
REPEATABLE_AUTOMATIC_FIELDS = frozenset({"when", "equipped"})


def _normalize_scalar(value: Scalar, channel: str, key: str) -> Scalar:
    if not isinstance(value, (int, float, bool, str)): raise TypeError(f"{channel}.{key} must be a scalar")
    if isinstance(value, str):
        value = value.strip().lower()
        if not value: raise ValueError(f"{channel}.{key} cannot be empty")
    return value


def _normalize_channel(source: Mapping[str, ChannelValue], allowed: frozenset[str], channel: str, repeatable: frozenset[str] = frozenset()) -> EffectChannel:
    if not isinstance(source, Mapping): raise TypeError(f"{channel} must be a dictionary")
    result: EffectChannel = {}
    for raw_key, raw_value in source.items():
        if not isinstance(raw_key, str): raise TypeError(f"{channel} keys must be strings")
        key = raw_key.strip().lower()
        if key not in allowed: raise ValueError(f"{key!r} is not valid in the {channel} channel")
        if isinstance(raw_value, list):
            if key not in repeatable: raise ValueError(f"{channel}.{key} does not accept multiple values")
            if not raw_value: raise ValueError(f"{channel}.{key} cannot be empty")
            result[key] = [_normalize_scalar(value, channel, key) for value in raw_value]
        else:
            result[key] = _normalize_scalar(raw_value, channel, key)
    return result


def _single(channel: Mapping[str, ChannelValue], key: str) -> Scalar | None:
    value = channel.get(key.lower())
    if isinstance(value, list): raise ValueError(f"{key!r} has multiple values")
    return value


def _values(channel: Mapping[str, ChannelValue], key: str) -> tuple[Scalar, ...]:
    value = channel.get(key.lower())
    if value is None: return ()
    return tuple(value) if isinstance(value, list) else (value,)


@dataclass(frozen=True, slots=True)
class EffectProgram:
    value: Scalar
    mode: EffectMode
    family: str
    maximum: float | None
    scales_with_rank: bool
    manual: EffectChannel
    automatic: EffectChannel

    def manual_value(self, key: str) -> Scalar | None:
        return _single(self.manual, key)

    def automatic_value(self, key: str) -> Scalar | None:
        return _single(self.automatic, key)

    def automatic_values(self, key: str) -> tuple[Scalar, ...]:
        return _values(self.automatic, key)


@dataclass(slots=True)
class Effect:
    properties: EffectChannel = field(default_factory=dict)
    manual: EffectChannel = field(default_factory=dict)
    automatic: EffectChannel = field(default_factory=dict)
    program: EffectProgram = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.properties = _normalize_channel(self.properties, PROPERTY_FIELDS, "properties")
        self.manual = _normalize_channel(self.manual, MANUAL_FIELDS, "manual")
        self.automatic = _normalize_channel(self.automatic, AUTOMATIC_FIELDS, "automatic", REPEATABLE_AUTOMATIC_FIELDS)
        manual_condition = _single(self.manual, "when")
        if isinstance(manual_condition, str) and manual_condition.startswith("on_"): raise ValueError("manual.when must omit the redundant 'on_' prefix")
        if "value" not in self.properties: raise ValueError("effect properties require value")
        mode_value = _single(self.properties, "mode")
        mode = "proportional" if mode_value is None else str(mode_value)
        if mode not in {"proportional", "base", "flat"}: raise ValueError(f"unsupported effect mode {mode!r}")
        family_value = _single(self.properties, "family")
        family = "common" if family_value is None else str(family_value)
        maximum_value = _single(self.properties, "max")
        maximum = None if maximum_value is None else float(maximum_value)
        rank_scale = _single(self.properties, "rank_scale")
        scales_with_rank = rank_scale not in {False, "false"}
        value = _single(self.properties, "value")
        assert value is not None
        self.program = EffectProgram(value, mode, family, maximum, scales_with_rank, deepcopy(self.manual), deepcopy(self.automatic))

    @classmethod
    def from_record(cls, record: Mapping[str, Mapping[str, ChannelValue]]) -> Effect:
        unknown = set(record) - {"properties", "manual", "automatic"}
        if unknown: raise TypeError(f"unknown effect fields: {', '.join(sorted(unknown))}")
        return cls(dict(record.get("properties", {})), dict(record.get("manual", {})), dict(record.get("automatic", {})))

    def to_record(self) -> dict[str, EffectChannel]:
        return {"properties": deepcopy(self.properties), "manual": deepcopy(self.manual), "automatic": deepcopy(self.automatic)}
