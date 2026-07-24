from collections.abc import Iterator, Mapping
from typing import Any, Self

from ..calculators.build_calculator import BuildCalculator
from .upgrade import Upgrade


class Build:
    results: BuildCalculator

    def __init__(self, *upgrades: Upgrade) -> None:
        self.upgrades = [upgrade.copy() for upgrade in upgrades]
        self.results = BuildCalculator(self)

    def __iter__(self) -> Iterator[Upgrade]:
        return (upgrade for upgrade in self.upgrades)

    def __len__(self) -> int:
        return len(self.upgrades)

    def __add__(self, other: Self | Upgrade) -> Self:
        return Build(*self, other) if isinstance(other, Upgrade) else Build(*self, *other)

    def __radd__(self, other: Upgrade) -> Self:
        return Build(other, *self)

    def __sub__(self, other: Self | Upgrade) -> Self:
        excluded = [other] if isinstance(other, Upgrade) else list(other)
        return Build(*(upgrade for upgrade in self if all(upgrade != item for item in excluded)))

    def configure(self, context: Mapping[str, Any] | None = None) -> Self:
        for upgrade in self.upgrades:
            upgrade.configure(context)
        self.results.resolve()
        return self

    def copy(self) -> Self:
        return type(self)(*self)
