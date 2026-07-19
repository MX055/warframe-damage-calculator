from collections.abc import Mapping
from typing import Self, overload

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from ..utils.types import JsonValue
from .build import Build
from .fields import WeaponData
from .upgrade import Upgrade


class Weapon:
    data_type = WeaponData
    calculator_type = WeaponCalculator
    formatter_type = WeaponFormatter

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.build = Build()
        self.data = self.data_type(data)
        self.stats = self.calculator_type(self)
        self.format = self.formatter_type(self)

    @overload
    def configure(self, build: Build, /) -> Self: ...

    @overload
    def configure(self, *upgrades: Upgrade) -> Self: ...

    def configure(self, *args: Build | Upgrade) -> Self:
        if len(args) == 1 and isinstance(args[0], Build): build = args[0]
        elif all(isinstance(arg, Upgrade) for arg in args): build = Build(*args)
        else: raise TypeError("configure() accepts one Build or multiple Upgrade instances")
        self.build = build
        self.stats.recompute()
        return self
