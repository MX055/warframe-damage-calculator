from __future__ import annotations

from typing import Unpack

from ..calculators import PrimaryCalculator
from ..formatters import PrimaryFormatter
from ..fields import PrimaryFields
from ..states import PrimaryState
from .ranged import Ranged


class Primary(Ranged):
    def __init__(self, **weapon_fields: Unpack[PrimaryFields]) -> None:
        base_state = self._create_state(PrimaryState, weapon_fields)
        self.stats: PrimaryCalculator = PrimaryCalculator(base_state)
        self.format: PrimaryFormatter = PrimaryFormatter(self.stats)
