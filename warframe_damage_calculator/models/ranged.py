from collections.abc import Mapping
from typing import Any

from ..calculators.ranged_calculator import RangedCalculator
from ..formatters.ranged_formatter import RangedFormatter
from .build import Build
from .data import Data
from .weapon import Weapon


class Ranged(Weapon):
    def __init__(self, data: Mapping[str, Any] | None = None):
        self.data = Data({"stats": {}, "context": {}} | dict(data or {}))
        self.build = Build()
        self.stats = RangedCalculator(self.data)
        self.format = RangedFormatter(self.stats)
