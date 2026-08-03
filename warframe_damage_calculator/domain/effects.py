from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, Self

from .scaled_values import Numeric, UpgradeValue, is_scaled_value_record, resolve_scalar


type Scalar = int | float | bool | str
type ChannelValue = Scalar | UpgradeValue | list[Scalar | UpgradeValue]
type EffectChannel = dict[str, ChannelValue]
type EffectMode = Literal["proportional", "multiplicative", "base", "flat"]

EFFECT_FIELDS = frozenset({"value", "mode", "family", "max", "when", "stacks", "for", "requires_rank", "automatic"})
AUTOMATIC_FIELDS = frozenset({"when", "on", "source", "stacks", "for", "chance", "multiply", "reset", "refresh", "equipped", "per"})
REPEATABLE_AUTOMATIC_FIELDS = frozenset({"when", "on", "equipped"})
AUTOMATIC_INIT_FIELDS = frozenset({"when", "on", "source", "stacks", "duration", "chance", "multiply", "reset", "refresh", "equipped", "per"})


@dataclass(frozen=True, slots=True)
class Source:
    path: str
    multiplier: Numeric | UpgradeValue = 1
    default: Scalar | None = None

    def __post_init__(self) -> None:
        if not self.path.startswith("$") or len(self.path) == 1: raise ValueError("source path must start with '$'")
        if isinstance(self.multiplier, bool) or not isinstance(self.multiplier, (int, float, UpgradeValue)): raise TypeError("source multiplier must be numeric or an upgrade value")

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Source:
        if set(record) - {"source", "multiplier", "default"} or not isinstance(record.get("source"), str): raise ValueError("source expressions only support source, multiplier, and default")
        raw_multiplier = record.get("multiplier", 1)
        if is_scaled_value_record(raw_multiplier):
            multiplier: Numeric | UpgradeValue = UpgradeValue.from_record(raw_multiplier, default_rank_scale=False)
        elif isinstance(raw_multiplier, (int, float)) and not isinstance(raw_multiplier, bool):
            multiplier = raw_multiplier
        else:
            raise TypeError("source multiplier must be numeric or an upgrade value")
        default = record.get("default")
        if default is not None and not isinstance(default, (int, float, bool, str)): raise TypeError("source default must be a scalar")
        return cls(str(record["source"]), multiplier, default)

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {"source": self.path}
        if isinstance(self.multiplier, UpgradeValue):
            record["multiplier"] = self.multiplier.to_record()
        elif self.multiplier != 1:
            record["multiplier"] = self.multiplier
        if self.default is not None: record["default"] = self.default
        return record

    def resolve_multiplier(self, rank: int, max_rank: int) -> float:
        return float(resolve_scalar(self.multiplier, rank, max_rank))


type EffectValue = Scalar | Source | UpgradeValue | dict[str, object]


def resolve_source(source: Source, namespaces: Mapping[str, object], *, rank: int = 0, max_rank: int = 0) -> object:
    path = source.path[1:]
    root, separator, remainder = path.partition(".")
    if root not in namespaces: raise ValueError(f"unknown source namespace ${root}")
    value = namespaces[root]
    segments: list[str | int] = []
    for component in remainder.split(".") if separator else ():
        name, _, indices = component.partition("[")
        if name: segments.append(name)
        while indices:
            index, closing, indices = indices.partition("]")
            if not closing or index == "" or not index.isdigit(): raise ValueError(f"invalid source path {source.path!r}")
            segments.append(int(index))
            if indices.startswith("["): indices = indices[1:]
            elif indices: raise ValueError(f"invalid source path {source.path!r}")
    for segment in segments:
        if isinstance(segment, int):
            if not isinstance(value, (list, tuple)): raise ValueError(f"source path {source.path!r} does not reference a sequence")
            try: value = value[segment]
            except IndexError: raise ValueError(f"source path {source.path!r} is out of range") from None
        elif isinstance(value, Mapping):
            if segment in value: value = value[segment]
            elif hasattr(value, segment): value = getattr(value, segment)
            elif source.default is not None: return deepcopy(source.default)
            else: raise ValueError(f"source path {source.path!r} does not exist")
        else:
            try: value = getattr(value, segment)
            except AttributeError: raise ValueError(f"source path {source.path!r} does not exist") from None
    multiplier = source.resolve_multiplier(rank, max_rank)
    if multiplier != 1:
        if not isinstance(value, (int, float)) or isinstance(value, bool): raise TypeError("source multiplier requires a numeric value")
        value = float(value) * multiplier
    return deepcopy(value)


def _normalize_scalar(value: Scalar, field_name: str) -> Scalar:
    if not isinstance(value, (int, float, bool, str)): raise TypeError(f"{field_name} must be a scalar")
    if isinstance(value, str):
        value = value.strip().lower()
        if not value: raise ValueError(f"{field_name} cannot be empty")
    return value


def _normalize_effect_value(value: EffectValue) -> EffectValue:
    if isinstance(value, UpgradeValue): return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value): raise TypeError("structured effect keys must be nonempty strings")
        if "source" in value: return Source.from_record(value)
        if is_scaled_value_record(value): return UpgradeValue.from_record(value)
        return deepcopy(dict(value))
    return value if isinstance(value, Source) else _normalize_scalar(value, "value")


def _normalize_channel_item(value: object, field_name: str) -> Scalar | UpgradeValue:
    if isinstance(value, UpgradeValue): return value
    if is_scaled_value_record(value): return UpgradeValue.from_record(value, default_rank_scale=False)
    if isinstance(value, (int, float)) and not isinstance(value, bool): return value
    if isinstance(value, (bool, str)): return _normalize_scalar(value, field_name)
    raise TypeError(f"{field_name} must be a scalar or upgrade value")


def _normalize_repeated(value: object, field_name: str) -> ChannelValue:
    if isinstance(value, (int, float, bool, str)) or isinstance(value, UpgradeValue) or is_scaled_value_record(value): return _normalize_channel_item(value, field_name)
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)): raise TypeError(f"{field_name} must be a scalar, upgrade value, or list")
    values = [_normalize_channel_item(item, field_name) for item in value]
    if not values: raise ValueError(f"{field_name} cannot be empty")
    return values


def _normalize_automatic(source: Mapping[str, object]) -> EffectChannel:
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
            result[key] = _normalize_channel_item(raw_value, f"automatic.{key}")
    return result


def _encode_channel_value(value: ChannelValue) -> object:
    if isinstance(value, UpgradeValue): return value.to_record()
    if isinstance(value, list): return [_encode_channel_value(item) for item in value]
    return deepcopy(value)


def resolve_channel_value(value: ChannelValue, rank: int, max_rank: int) -> Scalar | list[Scalar]:
    if isinstance(value, UpgradeValue): return resolve_scalar(value, rank, max_rank)
    if isinstance(value, list): return [resolve_channel_value(item, rank, max_rank) for item in value]
    return value


def resolve_automatic(automatic: EffectChannel, rank: int, max_rank: int) -> dict[str, Scalar | list[Scalar]]:
    return {key: resolve_channel_value(value, rank, max_rank) for key, value in automatic.items()}


@dataclass(slots=True)
class Automatic:
    when: ChannelValue | None = None
    on: ChannelValue | None = None
    source: ChannelValue | None = None
    stacks: ChannelValue | None = None
    duration: ChannelValue | None = None
    chance: ChannelValue | None = None
    multiply: ChannelValue | None = None
    reset: ChannelValue | None = None
    refresh: ChannelValue | None = None
    equipped: ChannelValue | None = None
    per: ChannelValue | None = None

    def to_channel(self) -> EffectChannel:
        raw: dict[str, object] = {}
        if self.when is not None: raw["when"] = self.when
        if self.on is not None: raw["on"] = self.on
        if self.source is not None: raw["source"] = self.source
        if self.stacks is not None: raw["stacks"] = self.stacks
        if self.duration is not None: raw["for"] = self.duration
        if self.chance is not None: raw["chance"] = self.chance
        if self.multiply is not None: raw["multiply"] = self.multiply
        if self.reset is not None: raw["reset"] = self.reset
        if self.refresh is not None: raw["refresh"] = self.refresh
        if self.equipped is not None: raw["equipped"] = self.equipped
        if self.per is not None: raw["per"] = self.per
        return _normalize_automatic(raw)

    def to_record(self) -> dict[str, object]:
        return {key: _encode_channel_value(value) for key, value in self.to_channel().items()}

    @classmethod
    def from_channel(cls, channel: Mapping[str, object]) -> Automatic:
        normalized = _normalize_automatic(channel)
        return cls(
            when=normalized.get("when"),
            on=normalized.get("on"),
            source=normalized.get("source"),
            stacks=normalized.get("stacks"),
            duration=normalized.get("for"),
            chance=normalized.get("chance"),
            multiply=normalized.get("multiply"),
            reset=normalized.get("reset"),
            refresh=normalized.get("refresh"),
            equipped=normalized.get("equipped"),
            per=normalized.get("per"),
        )

    @classmethod
    def from_record(cls, record: Mapping[str, object] | None) -> Automatic | None:
        if record is None: return None
        if not record: return Automatic()
        return cls.from_channel(record)


@dataclass(slots=True, init=False)
class Effect:
    value: EffectValue
    mode: EffectMode
    family: str
    maximum: float | None
    when: str | None
    stacks: Scalar | None
    duration: Scalar | UpgradeValue | None
    requires_rank: int | None
    automatic: EffectChannel = field(default_factory=dict)

    def __init__(self, value: EffectValue, *, mode: EffectMode = "proportional", family: str = "common", maximum: float | None = None, rank_scale: bool | None = None, when: str | None = None, stacks: Scalar | None = None, duration: Scalar | UpgradeValue | None = None, requires_rank: int | None = None, automatic: Automatic | Mapping[str, object] | None = None) -> None:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"proportional", "multiplicative", "base", "flat"}: raise ValueError(f"unsupported effect mode {normalized_mode!r}")
        if rank_scale is None and isinstance(value, (int, float)) and not isinstance(value, bool):
            rank_scale = True
        if rank_scale is True:
            if isinstance(value, bool) or not isinstance(value, (int, float)): raise TypeError("rank_scale convenience wrapping requires a numeric value")
            value = UpgradeValue(value, True)
        elif rank_scale is False:
            pass
        elif rank_scale is not None:
            raise TypeError("rank_scale must be a bool or None")
        normalized_value = _normalize_effect_value(value)
        if normalized_mode == "multiplicative" and not isinstance(normalized_value, (Source, UpgradeValue)) and (not isinstance(normalized_value, (int, float)) or isinstance(normalized_value, bool)): raise TypeError("multiplicative effect values must be numeric")
        normalized_family = str(family).strip().lower()
        if not normalized_family: raise ValueError("family cannot be empty")
        normalized_when = None if when is None else str(_normalize_scalar(when, "when"))
        if normalized_when is not None and normalized_when.startswith("on_"): raise ValueError("when must omit the redundant 'on_' prefix")
        self.value = normalized_value
        self.mode = normalized_mode
        self.family = normalized_family
        self.maximum = None if maximum is None else float(maximum)
        self.when = normalized_when
        self.stacks = None if stacks is None else _normalize_scalar(stacks, "stacks")
        if duration is None: self.duration = None
        elif isinstance(duration, UpgradeValue) or is_scaled_value_record(duration): self.duration = duration if isinstance(duration, UpgradeValue) else UpgradeValue.from_record(duration, default_rank_scale=False)
        elif isinstance(duration, (int, float)) and not isinstance(duration, bool): self.duration = duration
        else: self.duration = _normalize_scalar(duration, "duration")
        self.requires_rank = None if requires_rank is None else int(requires_rank)
        if automatic is None: self.automatic = {}
        elif isinstance(automatic, Automatic): self.automatic = automatic.to_channel()
        else: self.automatic = _normalize_automatic(automatic)

    def automate(self, *, when: object = None, on: object = None, source: object = None, stacks: object = None, duration: object = None, chance: object = None, multiply: object = None, reset: object = None, refresh: object = None, equipped: object = None, per: object = None) -> Self:
        self.automatic = Automatic(when=when, on=on, source=source, stacks=stacks, duration=duration, chance=chance, multiply=multiply, reset=reset, refresh=refresh, equipped=equipped, per=per).to_channel()
        return self

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Effect:
        unknown = set(record) - EFFECT_FIELDS
        if "rank_scale" in record: raise ValueError("entry-level rank_scale is not allowed; wrap individual numeric values")
        if unknown: raise TypeError(f"unknown effect fields: {', '.join(sorted(unknown))}")
        if "value" not in record: raise ValueError("effect requires value")
        raw_value = record["value"]
        if isinstance(raw_value, Mapping) or isinstance(raw_value, UpgradeValue):
            wrap = None
        elif isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            wrap = True
        else:
            wrap = False
        return cls(
            raw_value,
            mode=str(record.get("mode", "proportional")),
            family=str(record.get("family", "common")),
            maximum=None if record.get("max") is None else float(record["max"]),
            rank_scale=wrap,
            when=None if record.get("when") is None else str(record["when"]),
            stacks=record.get("stacks"),
            duration=record.get("for"),
            requires_rank=None if record.get("requires_rank") is None else int(record["requires_rank"]),
            automatic=record.get("automatic", {}),
        )

    def to_record(self) -> dict[str, object]:
        if isinstance(self.value, Source): encoded_value: object = self.value.to_record()
        elif isinstance(self.value, UpgradeValue): encoded_value = self.value.to_record()
        else: encoded_value = deepcopy(self.value)
        record: dict[str, object] = {"value": encoded_value}
        if self.mode != "proportional": record["mode"] = self.mode
        if self.family != "common": record["family"] = self.family
        if self.maximum is not None: record["max"] = self.maximum
        if self.when is not None: record["when"] = self.when
        if self.stacks is not None: record["stacks"] = deepcopy(self.stacks)
        if self.duration is not None: record["for"] = self.duration.to_record() if isinstance(self.duration, UpgradeValue) else deepcopy(self.duration)
        if self.requires_rank is not None: record["requires_rank"] = self.requires_rank
        record["automatic"] = {key: _encode_channel_value(value) for key, value in self.automatic.items()}
        return record
