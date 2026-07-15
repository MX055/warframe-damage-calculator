from collections.abc import Mapping
from typing import Any

from .data import Data


class Upgrade:
    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self.data = Data({"stats": {}, "context": {}} | dict(data or {}))

    def __getattr__(self, key: str) -> Any:
        return getattr(self.data, key)

    def copy(self) -> "Upgrade":
        return Upgrade(self.data)

    def resolve(self) -> "Upgrade":
        from ..calculators.upgrade_calculator import UpgradeCalculator
        return Upgrade(UpgradeCalculator(self).resolve())
