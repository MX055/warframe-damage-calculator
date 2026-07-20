from collections.abc import Iterator
from typing import Self

from ..calculators.build_calculator import BuildCalculator
from .upgrade import Upgrade


class Build:
    def __init__(self, *upgrades: Upgrade) -> None:
        self.upgrades = [upgrade.copy() for upgrade in upgrades]
        self.stats = BuildCalculator(self)

    def __iter__(self) -> Iterator[Upgrade]:
        return (upgrade.copy() for upgrade in self.upgrades)

    def __len__(self) -> int:
        return len(self.upgrades)

    def __add__(self, other: Self | Upgrade) -> Self:
        return Build(*self, other) if isinstance(other, Upgrade) else Build(*self, *other)

    def __radd__(self, other: Upgrade) -> Self:
        return Build(other, *self)

    def __sub__(self, other: Self | Upgrade) -> Self:
        excluded = [other] if isinstance(other, Upgrade) else list(other)
        names = {str(upgrade.data.name).casefold() for upgrade in excluded}
        return Build(*(upgrade for upgrade in self if str(upgrade.data.name).casefold() not in names))
    
    def copy(self) -> Self:
        return type(self)(*self)
