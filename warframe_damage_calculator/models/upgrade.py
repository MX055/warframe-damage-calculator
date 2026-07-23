from collections.abc import Mapping
from typing import Any, Self

from ..calculators.upgrade_calculator import UpgradeCalculator
from ..fields.upgrade import UpgradeData
from ..utils.types import JsonValue


class Upgrade:
    results: UpgradeCalculator

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = UpgradeData(data or {})
        self.results = UpgradeCalculator(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Upgrade):
            return NotImplemented
        return self.data == other.data

    def configure(self, context: Mapping[str, Any] | None = None) -> Self:
        if context is not None:
            self.data.runtime.update(context)
        self.results.resolve()
        return self

    def copy(self) -> Self:
        copied = type(self)(self.data.copy())
        copied.data.runtime.update(self.data.runtime.with_defaults())
        copied.results.resolve()
        return copied
