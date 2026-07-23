from collections.abc import Mapping
from typing import Self

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from ..utils.types import JsonValue
from .build import Build
from ..fields.weapon_data import WeaponData
from ..fields.weapon_input import WeaponStats


class Weapon:
    data_type = WeaponData
    mode_stats_type = WeaponStats
    calculator_type = WeaponCalculator
    formatter_type = WeaponFormatter

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = self.data_type(data or {})
        self.build = Build()
        self._attack = next(iter(self.data.attacks))
        self._evolutions: dict[int, int] = {}
        self.stats = self.calculator_type(self)
        self.format = self.formatter_type(self)

    def configure(self, build: Build | None = None, attack: str | None = None, evolutions: Mapping[int, int] | None = None) -> Self:
        if build is not None: self.build = build.copy()
        if attack is not None: self._attack = attack
        if evolutions is not None: self._evolutions = dict(evolutions)
        self.stats.recompute()
        return self
