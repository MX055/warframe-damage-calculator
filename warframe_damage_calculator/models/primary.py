from __future__ import annotations

from typing import Unpack

from ..calculators import PrimaryCalculator
from ..formatters import PrimaryFormatter
from ..fields import PrimaryField
from ..states import PrimaryState
from .ranged import Ranged


class Primary(Ranged):
    state_class = PrimaryState
    calculator_class = PrimaryCalculator
    formatter_class = PrimaryFormatter

    def __init__(self, **kwargs: Unpack[PrimaryField]) -> None:
        super().__init__(**kwargs)

    

    
    