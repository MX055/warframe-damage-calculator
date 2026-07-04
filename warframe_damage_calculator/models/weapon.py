from __future__ import annotations

from typing import Unpack

from ..calculators import WeaponCalculator
from ..formatters import WeaponFormatter
from ..fields import WeaponField
from ..states import WeaponState
from .build import Build


class Weapon:
    state_class = WeaponState
    calculator_class = WeaponCalculator
    formatter_class = WeaponFormatter

    def __init__(self, **kwargs: Unpack[WeaponField]):
        base = self.state_class(**kwargs)
        self.stats = self.calculator_class(base)
        self.format = self.formatter_class(self.stats)

    def configure(self, build: Build):
        self.stats.configure(build)
        return self