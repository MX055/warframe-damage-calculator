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
        excluded = [other.data] if isinstance(other, Upgrade) else other.data.upgrades
        return Build(*(Upgrade(data) for data in self.data.upgrades if data not in excluded))

    def resolve(self, weapon: Data | None = None) -> Build:
        return Build(*(upgrade.resolve(build=self.data, weapon=weapon) for upgrade in self))
        
    def aggregate(self) -> Data:
        stats = Data()
        for stat, value in (item for upgrade in self for item in upgrade.data.stats.items()):
            current = stats.get(stat)
            if current is None: stats[stat] = value
            elif isinstance(value, bool): stats[stat] = current or value
            else: stats[stat] = current + value
        return stats
    
    def get(self, stat: str, default: JsonScalar = 0) -> DataValue:
        return self.aggregate().get(stat, default)
