from __future__ import annotations

from typing import Unpack

from ..calculators import WeaponCalculator
from ..formatters import WeaponFormatter
from ..fields import WeaponField
from ..states import WeaponState
from .upgrade import Upgrade
from .build import Build


class Weapon:
    """Represents the base interface shared by weapon models.

    A weapon stores the starting stats passed to its constructor, creates the
    calculator that evaluates those stats, and creates the formatter that
    prints a readable summary.

    Use ``stats`` to access calculated values and ``format`` to access text
    output. Calling ``configure`` applies a ``Build`` and returns the same
    weapon so calls can be chained.

    Subclasses choose the state, calculator, and formatter used by each weapon
    family.
    """
    _state_class = WeaponState
    _calculator_class = WeaponCalculator
    _formatter_class = WeaponFormatter

    def __init__(self, **kwargs: Unpack[WeaponField]):
        base = self._state_class(**kwargs)
        self.stats = self._calculator_class(base)
        self.format = self._formatter_class(self.stats)

    def configure(self, *args: Build | Upgrade):
        if all(isinstance(arg, Upgrade) for arg in args): build = Build(*args)
        elif isinstance(args[0], Build) and len(args) == 1: build = args[0]
        else: raise TypeError
        self.stats.build = build
        self.stats.recompute()
        return self