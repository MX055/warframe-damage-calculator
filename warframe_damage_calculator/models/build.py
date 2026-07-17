from __future__ import annotations

from collections.abc import Iterator

from ..utils.types import JsonScalar
from .data import Data, DataValue
from .upgrade import Upgrade

class Build:
    def __init__(self, *upgrades: Upgrade) -> None:
        self.data = Data({"upgrades": [upgrade.data for upgrade in upgrades]})

    def __iter__(self) -> Iterator[Upgrade]:
        return (Upgrade(data) for data in self.data.upgrades)
    
    def __add__(self, other: Build | Upgrade) -> Build:
        return Build(*self, other) if isinstance(other, Upgrade) else Build(*self, *other)
    
    def __radd__(self, other: Upgrade) -> Build:
        return Build(other, *self)

    def __sub__(self, other: Build | Upgrade) -> Build:
        upgrades = list(self.data.upgrades)
        for excluded in (other,) if isinstance(other, Upgrade) else other:
            if (index := next((i for i, data in enumerate(upgrades) if data is excluded.data), None)) is not None:
                upgrades.pop(index)
        return Build(*(Upgrade(data) for data in upgrades))
        
    def aggregate(self) -> Data:
        stats = Data()
        for upgrade in self:
            for stat, value in upgrade.data.stats.items():
                current = stats.get(stat)
                stats[stat] = value if current is None else current or value if isinstance(value, bool) else current + value
        return stats
    
    def get(self, stat: str, default: JsonScalar = 0) -> DataValue:
        return self.aggregate().get(stat, default)
