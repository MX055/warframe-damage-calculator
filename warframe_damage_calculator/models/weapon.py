from collections.abc import Mapping
from typing import Any, overload, Self

from .data import Data
from .upgrade import Upgrade
from .build import Build
from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter


class Weapon:
    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | dict(data or {}))
        self.build = Build()
        self.stats = WeaponCalculator(self.data)
        self.format = WeaponFormatter(self.stats)

    @overload
    def configure(self, build: Build, /) -> Self: ...

    @overload
    def configure(self, *upgrades: Upgrade) -> Self: ...

    def configure(self, *args: Build | Upgrade) -> Self:
        if len(args) == 1 and isinstance(args[0], Build):
            build = args[0]
        elif all(isinstance(arg, Upgrade) for arg in args):
            build = Build(*args)
        else:
            raise TypeError("configure accepts one Build or multiple Upgrade instances")
        self.build = build
        self.stats.set_build(self.build)
        return self
