from __future__ import annotations

from typing import Unpack

from ..calculators import SecondaryCalculator
from ..formatters import SecondaryFormatter
from ..fields import SecondaryFields
from ..states import SecondaryState
from .ranged import Ranged


class Secondary(Ranged):
    """Represents a secondary weapon that can be configured and calculated.

    Secondary weapons use the ranged weapon inputs, then add
    secondary-specific calculations through ``SecondaryCalculator``.

    Mechanics such as Secondary Enervate and Secondary Encumber come from the
    active ``Build`` and are handled during calculation.

    Use this class when evaluating a secondary weapon build.
    """
    def __init__(self, **kwargs: Unpack[SecondaryFields]) -> None:
        base = SecondaryState(**kwargs)
        self.stats: SecondaryCalculator = SecondaryCalculator(base)
        self.format: SecondaryFormatter = SecondaryFormatter(self.stats)