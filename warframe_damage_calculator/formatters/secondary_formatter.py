from __future__ import annotations

from ..calculators import SecondaryCalculator
from ..states import SecondaryState
from .ranged_formatter import RangedFormatter


class SecondaryFormatter(RangedFormatter[SecondaryState]):
    def __init__(self, calculator: SecondaryCalculator) -> None:
        super().__init__(calculator)