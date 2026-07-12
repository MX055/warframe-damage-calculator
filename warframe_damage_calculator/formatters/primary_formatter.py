from __future__ import annotations

from ..calculators import PrimaryCalculator
from ..states import PrimaryState
from .ranged_formatter import RangedFormatter


class PrimaryFormatter(RangedFormatter[PrimaryState]):
    def __init__(self, calculator: PrimaryCalculator) -> None:
        super().__init__(calculator)