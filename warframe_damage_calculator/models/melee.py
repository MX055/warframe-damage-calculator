from __future__ import annotations

from typing import Unpack

from ..calculators import MeleeCalculator
from ..formatters import MeleeFormatter
from ..fields import MeleeFields
from ..states import MeleeState
from .weapon import Weapon


class Melee(Weapon):
    def __init__(self,  **kwargs: Unpack[MeleeFields]) -> None:
        base = MeleeState(**kwargs)
        self.stats: MeleeCalculator = MeleeCalculator(base)
        self.format: MeleeFormatter = MeleeFormatter(self.stats)
        
