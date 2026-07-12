from __future__ import annotations

from typing import Unpack

from ..calculators import RangedCalculator
from ..formatters import RangedFormatter
from ..fields import RangedFields
from ..states import RangedState
from .weapon import Weapon


class Ranged(Weapon):
    def __init__(self, **weapon_fields: Unpack[RangedFields]) -> None:
        base_state = self._create_state(RangedState, weapon_fields)
        self.stats: RangedCalculator = RangedCalculator(base_state)
        self.format: RangedFormatter = RangedFormatter(self.stats)

