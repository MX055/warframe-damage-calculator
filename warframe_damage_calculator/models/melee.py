from __future__ import annotations

from typing import Unpack

from ..calculators import MeleeCalculator
from ..formatters import MeleeFormatter
from ..fields import MeleeField
from ..states import MeleeState
from .weapon import Weapon


class Melee(Weapon):
    state_class = MeleeState
    calculator_class = MeleeCalculator
    formatter_class = MeleeFormatter

    def __init__(self,  **kwargs: Unpack[MeleeField]) -> None:
        super().__init__(**kwargs)

        