from __future__ import annotations

from dataclasses import MISSING, dataclass, fields
from typing import Iterator

from ..utils import UPGRADE_METADATA_FILEDS
from .dist import dist
from .upgrade import Upgrade


@dataclass(init=False)
class Build(Upgrade):
    def __init__(self, *upgrades: Upgrade) -> None:
        if any(not isinstance(upgrade, Upgrade) for upgrade in upgrades):
            raise TypeError
        self.upgrades = list(upgrades)

        for stat in fields(Upgrade):
            if stat.default_factory is not MISSING:
                default_value = stat.default_factory()
            else:
                default_value = stat.default
            values = [getattr(upgrade, stat.name) for upgrade in upgrades]

            if stat.name in UPGRADE_METADATA_FILEDS:
                setattr(self, stat.name, None)
                continue

            if not values:
                setattr(self, stat.name, default_value)
                continue

            if isinstance(default_value, bool):
                setattr(self, stat.name, any(values))
                continue

            if isinstance(default_value, dist):
                setattr(self, stat.name, sum(values, dist()))
                continue

            if isinstance(default_value, (int, float)):
                setattr(self, stat.name, sum(values))
                continue

            setattr(self, stat.name, default_value)

    def __add__(self, other: Upgrade | Build) -> Build:
        if isinstance(other, Upgrade):
            return Build(*[upgrade for upgrade in [*self.upgrades, other]])
        if isinstance(other, Build):
            return Build(*[upgrade for upgrade in [*self.upgrades, other.upgrades]])
        return NotImplemented
    
    def __radd__(self, other: Upgrade) -> Build:
        if isinstance(other, Upgrade):
            return Build(*[upgrade for upgrade in [other, *self.upgrades]])
        return NotImplemented
    
    def __sub__(self, other: Upgrade | Build) -> Build:
        if isinstance(other, Upgrade):
            return Build(*[upgrade for upgrade in self.upgrades if upgrade != other])
        if isinstance(other, Build):
            return Build(*[upgrade for upgrade in self.upgrades if upgrade not in other.upgrades])
        return NotImplemented
    
    def __iter__(self) -> Iterator[Upgrade]:
        return iter(self.upgrades)

