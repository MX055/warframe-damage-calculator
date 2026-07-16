from collections.abc import Mapping
from typing import Any

from ..calculators.primary_calculator import PrimaryCalculator
from ..formatters.primary_formatter import PrimaryFormatter
from .build import Build
from .data import Data
from .ranged import Ranged


class Primary(Ranged):
    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | dict(data or {}))
        self.build = Build()
        self.stats = PrimaryCalculator(self.data)
        self.format = PrimaryFormatter(self.stats)
