from collections.abc import Mapping
from typing import Self

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from ..utils.types import JsonValue
from .build import Build
from .fields import WeaponData, WeaponStats


class Weapon:
    data_type = WeaponData
    mode_stats_type = WeaponStats
    calculator_type = WeaponCalculator
    formatter_type = WeaponFormatter

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = self.data_type(data or {})
        self.build = Build()
        self.mode = next(iter(self.data.entry.attacks.values()))
        self.evolutions: dict[str, int] = {}
        self.stats = self.calculator_type(self)
        self.format = self.formatter_type(self)

    def configure(self, build: Build | None = None) -> Self:
        build = Build() if build is None else build
        self.build = build.copy()
        self.stats.recompute()
        return self

    def set_mode(self, name: str) -> Self:
        key = "_".join(name.casefold().replace("-", " ").split())
        self.mode = self.data.entry.attacks[key]
        self.stats.recompute()
        return self

    def set_evolutions(self, **selections: int) -> Self:
        self.evolutions.update(selections)
        self.stats.recompute()
        return self
