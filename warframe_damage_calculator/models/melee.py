from __future__ import annotations

from typing import Unpack

from ..calculators import MeleeCalculator
from ..formatters import MeleeFormatter
from ..fields import MeleeFields
from ..states import MeleeState
from .weapon import Weapon


class Melee(Weapon):
    def __init__(self, **weapon_fields: Unpack[MeleeFields]) -> None:
        base_state = self._create_state(MeleeState, weapon_fields)
        self.stats: MeleeCalculator = MeleeCalculator(base_state)
        self.format: MeleeFormatter = MeleeFormatter(self.stats)
