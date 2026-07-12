from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from .upgrade import Upgrade


@dataclass(init=False)
class Build:
    upgrades: list[Upgrade] = field(default_factory=list)

    def __init__(self, *upgrades: Upgrade) -> None:
        if any(not isinstance(upgrade, Upgrade) for upgrade in upgrades):
            raise TypeError("Build only accepts Upgrade objects")
        self.upgrades = list(upgrades)

    def __add__(self, other: Upgrade | Build) -> Build:
        if isinstance(other, Upgrade):
            return Build(*self.upgrades, other)
        if isinstance(other, Build):
            return Build(*self.upgrades, *other.upgrades)
        return NotImplemented

    def __radd__(self, other: Upgrade) -> Build:
        if isinstance(other, Upgrade):
            return Build(other, *self.upgrades)
        return NotImplemented

    def __sub__(self, other: Upgrade | Build) -> Build:
        excluded = {other} if isinstance(other, Upgrade) else set(other.upgrades) if isinstance(other, Build) else None
        if excluded is None:
            return NotImplemented
        return Build(*(upgrade for upgrade in self.upgrades if upgrade not in excluded))

    def __iter__(self) -> Iterator[Upgrade]:
        return iter(self.upgrades)

