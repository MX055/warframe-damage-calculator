from __future__ import annotations

from typing import Self, Unpack

from ..calculators import WeaponCalculator
from ..fields import WeaponFields
from ..formatters import WeaponFormatter
from ..states import WeaponState
from .upgrade import Upgrade
from .build import Build


class Weapon:
    def __init__(self, **kwargs: Unpack[WeaponFields]):
        base = WeaponState(**kwargs)
        self.stats = WeaponCalculator(base)
        self.format = WeaponFormatter(self.stats)

    def configure(self, *args: Build | Upgrade) -> Self:
        if all(type(arg) is Upgrade for arg in args): build = Build(*args)
        elif isinstance(args[0], Build) and len(args) == 1: build = args[0]
        else: raise TypeError
        self.stats.build = build
        self.stats.recompute()
        return self