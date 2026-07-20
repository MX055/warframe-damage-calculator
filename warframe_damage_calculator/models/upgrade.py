from collections.abc import Mapping
from typing import Self

from ..calculators.upgrade_calculator import UpgradeCalculator
from ..utils.types import JsonValue
from .fields import UpgradeData


class Upgrade:
    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = UpgradeData(data or {})
        self.stats = UpgradeCalculator(self)

    def copy(self) -> Self:
        copied = type(self)(self.data.copy())
        copied.data.runtime.update(self.data.runtime.with_defaults())
        copied.stats.resolve()
        return copied
