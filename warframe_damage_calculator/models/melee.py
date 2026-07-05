from __future__ import annotations

from typing import Unpack

from ..calculators import MeleeCalculator
from ..formatters import MeleeFormatter
from ..fields import MeleeFields
from ..states import MeleeState
from .weapon import Weapon


class Melee(Weapon):
    """Represents a melee weapon that can be configured and calculated.

    Melee weapons use the shared weapon inputs plus attack speed, then add
    melee-specific calculations through ``MeleeCalculator``.

    Mechanics such as Melee Duplicate and Melee Doughty come from the active
    ``Build`` and are handled during calculation.

    Use this class when evaluating a melee weapon build.
    """
    def __init__(self,  **kwargs: Unpack[MeleeFields]) -> None:
        base = MeleeState(**kwargs)
        self.stats: MeleeCalculator = MeleeCalculator(base)
        self.format: MeleeFormatter = MeleeFormatter(self.stats)
        
