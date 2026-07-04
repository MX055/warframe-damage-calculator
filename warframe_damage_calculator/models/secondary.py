from __future__ import annotations

from typing import Unpack

from ..calculators import SecondaryCalculator
from ..formatters import SecondaryFormatter
from ..fields import SecondaryField
from ..states import SecondaryState
from .ranged import Ranged


class Secondary(Ranged):
    state_class = SecondaryState
    calculator_class = SecondaryCalculator
    formatter_class = SecondaryFormatter

    def __init__(self, **kwargs: Unpack[SecondaryField]) -> None:
        super().__init__(**kwargs)