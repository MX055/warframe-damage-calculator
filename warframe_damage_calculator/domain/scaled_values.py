from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


type Numeric = int | float
type EffectMode = Literal["proportional", "multiplicative", "base", "flat"]


@dataclass(frozen=True, slots=True)
class UpgradeValue:
    value: Numeric
    rank_scale: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)): raise TypeError("scaled value must be numeric")
        if not isinstance(self.rank_scale, bool): raise TypeError("rank_scale must be a bool")

    @classmethod
    def from_record(cls, record: Mapping[str, object], *, default_rank_scale: bool = True) -> UpgradeValue:
        if "value" not in record or set(record) - {"value", "rank_scale"}: raise ValueError("scaled value requires value and optional rank_scale")
        value = record["value"]
        rank_scale = record.get("rank_scale", default_rank_scale)
        if isinstance(value, bool) or not isinstance(value, (int, float)): raise TypeError("scaled value must be numeric")
        if not isinstance(rank_scale, bool): raise TypeError("rank_scale must be a bool")
        return cls(value, rank_scale)

    def to_record(self) -> dict[str, Numeric | bool]:
        return {"value": self.value, "rank_scale": self.rank_scale}


ScaledValue = UpgradeValue


def rank_factor(rank: int, max_rank: int) -> float:
    if max_rank < 0: raise ValueError("max_rank must be nonnegative")
    selected = min(max(int(rank), 0), int(max_rank))
    return 1.0 if max_rank == 0 else (selected + 1) / (max_rank + 1)


def resolve_scalar(value: Numeric | UpgradeValue, rank: int, max_rank: int, *, mode: EffectMode = "proportional") -> Numeric:
    if isinstance(value, bool) or not isinstance(value, (int, float, UpgradeValue)): raise TypeError("resolve_scalar requires a numeric value or upgrade value")
    if isinstance(value, (int, float)): return value
    if not value.rank_scale: return value.value
    factor = rank_factor(rank, max_rank)
    raw = value.value
    if mode == "multiplicative": resolved = 1 + (float(raw) - 1) * factor
    else: resolved = float(raw) * factor
    if isinstance(raw, int) and not isinstance(raw, bool) and float(resolved).is_integer(): return int(resolved)
    return resolved


def is_scaled_value_record(value: object) -> bool:
    if not isinstance(value, Mapping) or "source" in value or "value" not in value: return False
    return set(value) <= {"value", "rank_scale"} and (isinstance(value["value"], (int, float)) and not isinstance(value["value"], bool))
