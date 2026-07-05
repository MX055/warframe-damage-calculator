from __future__ import annotations

from typing import Self, Unpack

from ..calculators import WeaponCalculator
from ..fields import WeaponFields
from ..formatters import WeaponFormatter
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
    def __init__(self, **kwargs: Unpack[WeaponFields]):
        base = WeaponState(**kwargs)
        self.stats = WeaponCalculator(base)
        self.format = WeaponFormatter(self.stats)

    def configure(self, *args: Build | Upgrade) -> Self:
        if all(isinstance(arg, Upgrade) for arg in args): build = Build(*args)
        elif isinstance(args[0], Build) and len(args) == 1: build = args[0]
        else: raise TypeError
        self.stats.build = build
        self.stats.recompute()
        return self