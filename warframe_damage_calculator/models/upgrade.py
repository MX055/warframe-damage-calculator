from collections.abc import Mapping
from typing import Any, Self

from ..calculators.upgrade_calculator import UpgradeCalculator
from ..utils.types import JsonValue
from ..fields.upgrade import UpgradeData


class Upgrade:
    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = UpgradeData(data or {})
        self.stats = UpgradeCalculator(self)

    def configure(self, context: Mapping[str, Any] | None = None) -> Self:
        if context is not None: self.data.runtime.update(context)
        self.stats.resolve()
        return self

    def copy(self) -> Self:
        copied = type(self)(self.data.copy())
        copied.data.runtime.update(self.data.runtime.with_defaults())
        copied.stats.resolve()
        return copied
