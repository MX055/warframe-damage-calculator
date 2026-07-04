from __future__ import annotations

from typing import Unpack

from ..calculators import RangedCalculator
from ..formatters import RangedFormatter
from ..fields import RangedField
from ..states import RangedState
from .weapon import Weapon


class Ranged(Weapon):
    state_class = RangedState
    calculator_class = RangedCalculator
    formatter_class = RangedFormatter

    def __init__(self, **kwargs: Unpack[RangedField]) -> None:
        super().__init__(**kwargs)

