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
        own = self.data.with_defaults()
        theirs = other.data.with_defaults()
        own.pop("runtime", None)
        theirs.pop("runtime", None)
        return own == theirs

    def set(self, context: Mapping[str, Any] | None = None) -> Self:
        if context is not None:
            self.data.runtime.update(context)
        self.results.resolve()
        return self

    def copy(self) -> Self:
        return type(self)(self.data.copy())
