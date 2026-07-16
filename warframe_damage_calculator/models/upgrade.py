from __future__ import annotations

from ..calculators.upgrade_calculator import UpgradeCalculator
from ..utils.types import JsonValue
from .data import Data


class Upgrade:
    def __init__(self, data: dict[str, JsonValue] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | (data or {}))

    def copy(self) -> Upgrade:
        return Upgrade(self.data)

    @property
    def stats(self) -> Data:
        return self.data.stats

    @property
    def context(self) -> Data:
        return self.data.context

    def resolve(self) -> Upgrade:
        return Upgrade(UpgradeCalculator(self.data).resolve())
