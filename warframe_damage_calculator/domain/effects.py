from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal, Self


class Placeholder:
    __slots__ = ()

    def __repr__(self) -> str:
        return "PLACEHOLDER"

    def __copy__(self) -> Placeholder:
        return self

    def __deepcopy__(self, memo: dict) -> Placeholder:
        return self


PLACEHOLDER = Placeholder()

type Scalar = int | float | bool | str
type EffectValue = Scalar | Placeholder
type ChannelValue = Scalar | list[Scalar]
type EffectChannel = dict[str, ChannelValue]
type EffectMode = Literal["proportional", "multiplicative", "base", "flat"]

EFFECT_FIELDS = frozenset({"value", "mode", "family", "max", "rank_scale", "when", "stacks", "for", "requires_rank", "automatic"})
AUTOMATIC_FIELDS = frozenset({"when", "on", "with", "stacks", "for", "chance", "multiply", "reset", "equipped", "per"})
REPEATABLE_AUTOMATIC_FIELDS = frozenset({"when", "equipped"})


def _normalize_scalar(value: Scalar, field_name: str) -> Scalar:
    if not isinstance(value, (int, float, bool, str)): raise TypeError(f"{field_name} must be a scalar")
    if isinstance(value, str):
        value = value.strip().lower()
        if not value: raise ValueError(f"{field_name} cannot be empty")
    return value


def _normalize_effect_value(value: EffectValue) -> EffectValue:
    return value if value is PLACEHOLDER else _normalize_scalar(value, "value")


def _normalize_repeated(value: Scalar | Iterable[Scalar], field_name: str) -> ChannelValue:
    if isinstance(value, (int, float, bool, str)): return _normalize_scalar(value, field_name)
    values = [_normalize_scalar(item, field_name) for item in value]
    if not values: raise ValueError(f"{field_name} cannot be empty")
    return values


def _normalize_automatic(source: Mapping[str, ChannelValue]) -> EffectChannel:
    if not isinstance(source, Mapping): raise TypeError("automatic must be a dictionary")
    result: EffectChannel = {}
    for raw_key, raw_value in source.items():
        if not isinstance(raw_key, str): raise TypeError("automatic keys must be strings")
        key = raw_key.strip().lower()
        if key not in AUTOMATIC_FIELDS: raise ValueError(f"{key!r} is not a valid automatic field")
        if isinstance(raw_value, list):
            if key not in REPEATABLE_AUTOMATIC_FIELDS: raise ValueError(f"automatic.{key} does not accept multiple values")
            result[key] = _normalize_repeated(raw_value, f"automatic.{key}")
        else:
            result[key] = _normalize_scalar(raw_value, f"automatic.{key}")
    return result


@dataclass(slots=True, init=False)
class Effect:
    value: EffectValue
    mode: EffectMode
    family: str
    maximum: float | None
    scales_with_rank: bool
    when: str | None
    stacks: Scalar | None
    duration: Scalar | None
    requires_rank: int | None
    automatic: EffectChannel = field(default_factory=dict)

    def __init__(self, value: EffectValue, *, mode: EffectMode = "proportional", family: str = "common", maximum: float | None = None, rank_scale: bool = True, when: str | None = None, stacks: Scalar | None = None, duration: Scalar | None = None, requires_rank: int | None = None) -> None:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"proportional", "multiplicative", "base", "flat"}: raise ValueError(f"unsupported effect mode {normalized_mode!r}")
        if normalized_mode == "multiplicative" and value is not PLACEHOLDER and (not isinstance(value, (int, float)) or isinstance(value, bool)): raise TypeError("multiplicative effect values must be numeric")
        normalized_family = str(family).strip().lower()
        if not normalized_family: raise ValueError("family cannot be empty")
        normalized_when = None if when is None else str(_normalize_scalar(when, "when"))
        if normalized_when is not None and normalized_when.startswith("on_"): raise ValueError("when must omit the redundant 'on_' prefix")
        self.value = _normalize_effect_value(value)
        self.mode = normalized_mode
        self.family = normalized_family
        self.maximum = None if maximum is None else float(maximum)
        self.scales_with_rank = bool(rank_scale)
        self.when = normalized_when
        self.stacks = None if stacks is None else _normalize_scalar(stacks, "stacks")
        self.duration = None if duration is None else _normalize_scalar(duration, "duration")
        self.requires_rank = None if requires_rank is None else int(requires_rank)
        self.automatic = {}

    def automate(self, *, when: Scalar | Iterable[Scalar] | None = None, on: Scalar | None = None, with_: Scalar | None = None, stacks: Scalar | None = None, duration: Scalar | None = None, chance: Scalar | None = None, multiply: Scalar | None = None, reset: Scalar | None = None, equipped: Scalar | Iterable[Scalar] | None = None, per: Scalar | None = None) -> Self:
        automatic: EffectChannel = {}
        if when is not None: automatic["when"] = _normalize_repeated(when, "automatic.when")
        if on is not None: automatic["on"] = _normalize_scalar(on, "automatic.on")
        if with_ is not None: automatic["with"] = _normalize_scalar(with_, "automatic.with")
        if stacks is not None: automatic["stacks"] = _normalize_scalar(stacks, "automatic.stacks")
        if duration is not None: automatic["for"] = _normalize_scalar(duration, "automatic.for")
        if chance is not None: automatic["chance"] = _normalize_scalar(chance, "automatic.chance")
        if multiply is not None: automatic["multiply"] = _normalize_scalar(multiply, "automatic.multiply")
        if reset is not None: automatic["reset"] = _normalize_scalar(reset, "automatic.reset")
        if equipped is not None: automatic["equipped"] = _normalize_repeated(equipped, "automatic.equipped")
        if per is not None: automatic["per"] = _normalize_scalar(per, "automatic.per")
        self.automatic = automatic
        return self

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Effect:
        unknown = set(record) - EFFECT_FIELDS
        if unknown: raise TypeError(f"unknown effect fields: {', '.join(sorted(unknown))}")
        if "value" not in record: raise ValueError("effect requires value")
        effect = cls(
            record["value"],
            mode=str(record.get("mode", "proportional")),
            family=str(record.get("family", "common")),
            maximum=None if record.get("max") is None else float(record["max"]),
            rank_scale=record.get("rank_scale", True) not in {False, "false"},
            when=None if record.get("when") is None else str(record["when"]),
            stacks=record.get("stacks"),
            duration=record.get("for"),
            requires_rank=None if record.get("requires_rank") is None else int(record["requires_rank"]),
        )
        automatic = record.get("automatic", {})
        if not isinstance(automatic, Mapping): raise TypeError("automatic must be a dictionary")
        effect.automatic = _normalize_automatic(automatic)
        return effect

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {"value": "$weapon" if self.value is PLACEHOLDER else deepcopy(self.value)}
        if self.mode != "proportional": record["mode"] = self.mode
        if self.family != "common": record["family"] = self.family
        if self.maximum is not None: record["max"] = self.maximum
        if not self.scales_with_rank: record["rank_scale"] = False
        if self.when is not None: record["when"] = self.when
        if self.stacks is not None: record["stacks"] = deepcopy(self.stacks)
        if self.duration is not None: record["for"] = deepcopy(self.duration)
        if self.requires_rank is not None: record["requires_rank"] = self.requires_rank
        record["automatic"] = deepcopy(self.automatic)
        return record
