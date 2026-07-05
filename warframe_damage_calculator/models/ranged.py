from __future__ import annotations

from typing import Unpack

from ..calculators import RangedCalculator
from ..formatters import RangedFormatter
from ..fields import RangedFields
from ..states import RangedState
from .weapon import Weapon


class Ranged(Weapon):
    """Represents the base model for ranged weapons.

    Ranged weapons add stats such as fire rate, reload speed, magazine size,
    multishot, weakpoint damage, beam behavior, battery behavior, and
    explosion damage.

    Connects those inputs to ``RangedCalculator`` and ``RangedFormatter``
    while keeping the same ``configure`` workflow as ``Weapon``.

    ``Primary`` and ``Secondary`` build on this class for their own mechanics.
    """
    def __init__(self, **kwargs: Unpack[RangedFields]) -> None:
        base = RangedState(**kwargs)
        self.stats: RangedCalculator = RangedCalculator(base)
        self.format: RangedFormatter = RangedFormatter(self.stats)

