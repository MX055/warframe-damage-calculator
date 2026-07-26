from collections.abc import Mapping
from typing import Any, Self

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from ..utils.types import JsonValue
from .build import Build
from .upgrade import Upgrade
from ..fields.weapon_data import WeaponData
from ..fields.weapon_input import WeaponStats


class Weapon:
    data_type = WeaponData
    stats_type = WeaponStats
    calculator_type = WeaponCalculator
    formatter_type = WeaponFormatter

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = self.data_type(data or {})
        self.build = Build()
        self.results = self.calculator_type(self)
        self.format = self.formatter_type(self)

    def configure(self, build: Build | Upgrade | None = None) -> Self:
        if build is not None:
            self.build = build.copy() if isinstance(build, Build) else Build(build)
        self.results.resolve()
        return self

    def set(self, context: Mapping[str, Any] | None = None) -> Self:
        if context is not None:
            self.data.runtime.update(context)
        self.results.resolve()
        return self

    def copy(self) -> Self:
        copied = type(self)(self.data.copy())
        copied.build = self.build.copy()
        copied.results.resolve()
        return copied
