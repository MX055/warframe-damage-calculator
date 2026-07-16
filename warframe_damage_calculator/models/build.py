from __future__ import annotations

from collections.abc import Iterator

from ..utils.types import JsonScalar
from .data import Data, DataValue
from .upgrade import Upgrade

class Build:
    def __init__(self, *upgrades: Upgrade) -> None:
        self.upgrades = list(upgrades)

    def __iter__(self) -> Iterator[Upgrade]:
        return iter(self.upgrades)
    
    def __add__(self, other: Build | Upgrade) -> Build:
        return Build(*self, other) if isinstance(other, Upgrade) else Build(*self, *other)
    
    def __radd__(self, other: Upgrade) -> Build:
        return Build(other, *self)

    def __sub__(self, other: Build | Upgrade) -> Build:
        excluded = {other} if isinstance(other, Upgrade) else set(other)
        return Build(*(upgrade for upgrade in self if upgrade not in excluded))
    
    def aggregate(self) -> Data:
        stats = Data()
        for upgrade in self:
            for stat, value in upgrade.stats.items():
                current = stats.get(stat)
                stats[stat] = value if current is None else current or value if isinstance(value, bool) else current + value
        return stats
    
    def get(self, stat: str, default: JsonScalar = 0) -> DataValue:
        return self.aggregate().get(stat, default)
