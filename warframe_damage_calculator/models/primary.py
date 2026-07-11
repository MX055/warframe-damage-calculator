from __future__ import annotations

from typing import Unpack

from ..calculators import PrimaryCalculator
from ..formatters import PrimaryFormatter
from ..fields import PrimaryFields
from ..states import PrimaryState
from .ranged import Ranged


class Primary(Ranged):
    def __init__(self, **kwargs: Unpack[PrimaryFields]) -> None:
        base = PrimaryState(**kwargs)
        self.stats: PrimaryCalculator = PrimaryCalculator(base)
        self.format: PrimaryFormatter = PrimaryFormatter(self.stats)
    



    

    
