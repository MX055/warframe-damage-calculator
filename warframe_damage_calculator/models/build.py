from collections.abc import Iterator
from typing import Self

from ..calculators.build_calculator import BuildCalculator
from .fields import BuildData
from .upgrade import Upgrade


class Build:
    def __init__(self, *upgrades: Upgrade) -> None:
        self.data = BuildData({"upgrades": [upgrade.data.copy() for upgrade in upgrades]})
        self.stats = BuildCalculator(self)

    def __iter__(self) -> Iterator[Upgrade]:
        return (Upgrade(data) for data in self.data.upgrades)

    def __len__(self) -> int:
        return len(self.data.upgrades)

    def __add__(self, other: Self | Upgrade) -> Self:
        return Build(*self, other) if isinstance(other, Upgrade) else Build(*self, *other)

    def __radd__(self, other: Upgrade) -> Self:
        return Build(other, *self)

    def __sub__(self, other: Self | Upgrade) -> Self:
        excluded = [other.data] if isinstance(other, Upgrade) else [upgrade.data for upgrade in other]
        return Build(*(upgrade for upgrade in self if upgrade.data not in excluded))
