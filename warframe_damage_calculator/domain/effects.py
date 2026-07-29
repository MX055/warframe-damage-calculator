from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


type Scalar = int | float | bool | str
type EffectMode = Literal["proportional", "base", "flat"]

PROPERTY_OPS = frozenset({"VALUE", "MODE", "FAMILY", "MAX", "RANK_SCALE"})
MANUAL_OPS = frozenset({"WHEN", "STACKS", "FOR", "REQUIRES_RANK"})
AUTOMATIC_OPS = frozenset({"WHEN", "ON", "WITH", "STACKS", "FOR", "CHANCE", "IF", "MULTIPLY", "RESET", "EQUIPPED", "SCOPE", "EXCLUDE", "TARGET", "APPLY_MODE", "PER"})


@dataclass(frozen=True, slots=True)
class Token:
    op: str
    value: str

    @classmethod
    def parse(cls, source: str, allowed: frozenset[str], channel: str) -> Token:
        if not isinstance(source, str) or ":" not in source: raise ValueError(f"{channel} token must use OP:VALUE: {source!r}")
        op, value = (part.strip() for part in source.split(":", 1))
        op = op.upper()
        if op not in allowed: raise ValueError(f"{op!r} is not valid in the {channel} channel")
        if not value: raise ValueError(f"{channel} token has an empty operand: {source!r}")
        return cls(op, value.upper())


@dataclass(frozen=True, slots=True)
class EffectProgram:
    value: Scalar
    mode: EffectMode
    family: str
    maximum: float | None
    scales_with_rank: bool
    manual: tuple[Token, ...]
    automatic: tuple[Token, ...]

    def manual_value(self, op: str) -> str | None:
        return next((token.value for token in self.manual if token.op == op), None)

    def automatic_values(self, op: str) -> tuple[str, ...]:
        return tuple(token.value for token in self.automatic if token.op == op)


def _parse_scalar(source: str) -> Scalar:
    if source == "TRUE": return True
    if source == "FALSE": return False
    try: return int(source)
    except ValueError:
        try: return float(source)
        except ValueError: return source.lower()


def _parse_channel(source: list[str], allowed: frozenset[str], channel: str, repeatable: frozenset[str] = frozenset()) -> tuple[Token, ...]:
    tokens = tuple(Token.parse(value, allowed, channel) for value in source)
    singular = [token.op for token in tokens if token.op not in repeatable]
    duplicates = {op for op in singular if singular.count(op) > 1}
    if duplicates: raise ValueError(f"duplicate {channel} tokens: {', '.join(sorted(duplicates))}")
    return tokens


@dataclass(slots=True)
class Effect:
    properties: list[str] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)
    automatic: list[str] = field(default_factory=list)
    program: EffectProgram = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.properties = list(self.properties)
        self.manual = list(self.manual)
        self.automatic = list(self.automatic)
        properties = _parse_channel(self.properties, PROPERTY_OPS, "properties")
        values = {token.op: token.value for token in properties}
        if "VALUE" not in values: raise ValueError("effect properties require VALUE")
        mode = values.get("MODE", "PROPORTIONAL").lower()
        if mode not in {"proportional", "base", "flat"}: raise ValueError(f"unsupported effect mode {mode!r}")
        manual = _parse_channel(self.manual, MANUAL_OPS, "manual")
        automatic = _parse_channel(self.automatic, AUTOMATIC_OPS, "automatic", frozenset({"EQUIPPED", "SCOPE", "EXCLUDE"}))
        maximum = float(values["MAX"]) if "MAX" in values else None
        self.program = EffectProgram(_parse_scalar(values["VALUE"]), mode, values.get("FAMILY", "COMMON").lower(), maximum, values.get("RANK_SCALE", "TRUE") == "TRUE", manual, automatic)

    @classmethod
    def from_record(cls, record: dict[str, list[str]]) -> Effect:
        unknown = set(record) - {"properties", "manual", "automatic"}
        if unknown: raise TypeError(f"unknown effect fields: {', '.join(sorted(unknown))}")
        return cls(record.get("properties", []), record.get("manual", []), record.get("automatic", []))

    def to_record(self) -> dict[str, list[str]]:
        return {"properties": list(self.properties), "manual": list(self.manual), "automatic": list(self.automatic)}
