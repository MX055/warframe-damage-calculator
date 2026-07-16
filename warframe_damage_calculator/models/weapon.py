from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from .build import Build
from .data import Data
from .upgrade import Upgrade


class Weapon:
    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | dict(data or {}))
        self.build = Build()
        self.stats = WeaponCalculator(self.data)
        self.format = WeaponFormatter(self.stats)

    def configure(self, *args: Build | Upgrade) -> Self:
        build = args[0] if len(args) == 1 and isinstance(args[0], Build) else Build(*args)
        self.build = build
        self.stats.set_build(self.build)
        return self
