from __future__ import annotations

from typing import Unpack

from ..calculators import SecondaryCalculator
from ..formatters import SecondaryFormatter
from ..fields import SecondaryFields
from ..states import SecondaryState
from .ranged import Ranged


class Secondary(Ranged):
    def __init__(self, **weapon_fields: Unpack[SecondaryFields]) -> None:
        base_state = self._create_state(SecondaryState, weapon_fields)
        self.stats: SecondaryCalculator = SecondaryCalculator(base_state)
        self.format: SecondaryFormatter = SecondaryFormatter(self.stats)
