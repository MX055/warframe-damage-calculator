from collections.abc import Mapping
from typing import Any, Self

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from ..utils.constants import MAX_COMBO_MULTIPLIER
from ..utils.functions import clamp
from ..utils.types import JsonValue
from .build import Build
from ..fields.weapon_data import WeaponData
from ..fields.weapon_input import WeaponStats


class Weapon:
    data_type = WeaponData
    stats_type = WeaponStats
    calculator_type = WeaponCalculator
    formatter_type = WeaponFormatter

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = self.data_type(data or {})
        self.build = Build()
        self.results = self.calculator_type(self)
        self.format = self.formatter_type(self)

    @staticmethod
    def _normalize_runtime_context(context: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(context)
        if "combo" in normalized and normalized["combo"] is not None:
            normalized["combo"] = int(clamp(int(normalized["combo"]), 1, MAX_COMBO_MULTIPLIER))
        if "evolutions" in normalized and normalized["evolutions"] is not None:
            normalized["evolutions"] = dict(normalized["evolutions"])
        return normalized

    def configure(self, build: Build | None = None, context: Mapping[str, Any] | None = None) -> Self:
        if build is not None:
            self.build = build.copy()
        if context is not None:
            self.data.runtime.update(self._normalize_runtime_context(context))
        self.results.resolve()
        return self

    def copy(self) -> Self:
        copied = type(self)(self.data.copy())
        copied.build = self.build.copy()
        copied.data.runtime.update(self.data.runtime.with_defaults())
        copied.results.resolve()
        return copied
