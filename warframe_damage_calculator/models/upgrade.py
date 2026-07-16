from __future__ import annotations

from ..utils.types import JsonValue
from .data import Data
from ..calculators.upgrade_calculator import UpgradeCalculator


class Upgrade:
    def __init__(self, data: dict[str, JsonValue] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | (data or {}))

    def copy(self) -> Upgrade:
        return Upgrade(self.data)

    def resolve(self) -> Upgrade:
        return Upgrade(UpgradeCalculator(self.data).resolve())
