from __future__ import annotations

from ..utils.types import JsonValue
from .data import Data
from ..calculators.upgrade_calculator import UpgradeCalculator


class Upgrade:
    def __init__(self, data: dict[str, JsonValue] | Data | None = None) -> None:
        self.data = data if isinstance(data, Data) else Data({"stats": {}, "context": {}} | (data or {}))

    def copy(self) -> Upgrade:
        return Upgrade(self.data)

    def resolve(self, weapon: Data | None = None, build: Data | None = None) -> Upgrade:
        return Upgrade(UpgradeCalculator(upgrade=self.data, weapon=weapon, build=build).resolve())
