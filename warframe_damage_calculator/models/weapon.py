from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self

from ..calculators import WeaponCalculator
from ..formatters import WeaponFormatter
from .build import Build
from .data import Data
from .upgrade import Upgrade


class Weapon:
    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | dict(data or {}))
        self.build = Build()
        self.calculator = WeaponCalculator(self.data.stats, self.data.context)
        self.format = WeaponFormatter(self.calculator)

    @property
    def stats(self) -> Data: return self.data.stats

    @property
    def context(self) -> Data: return self.data.context

    def configure(self, *args: Build | Upgrade) -> Self:
        build = args[0] if len(args) == 1 and isinstance(args[0], Build) else Build(*args)
        self.build = build
        self.calculator.set_build(self.build)
        return self
