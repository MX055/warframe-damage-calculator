from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from .dist import dist


StatValue: TypeAlias = float | int | bool | dist
ConditionalStat: TypeAlias = tuple[StatValue, str]


@dataclass(eq=False)
class Upgrade:
    """Data-only definition of an upgrade and its three stat buckets."""

    name: str | None = None
    category: str | None = None
    compatibility: set[str] = field(default_factory=set)
    incompatibility: set[str] = field(default_factory=set)
    requirements: dict[str, object] = field(default_factory=dict)
    max_rank: int | None = None
    max_stacks: int | None = None
    is_exilus: bool = False

    stats: dict[str, StatValue] = field(default_factory=dict)
    conditional_stats: dict[str, ConditionalStat] = field(default_factory=dict)
    stacking_stats: dict[str, ConditionalStat] = field(default_factory=dict)
