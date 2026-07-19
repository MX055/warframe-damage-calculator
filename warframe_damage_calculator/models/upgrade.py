from collections.abc import Mapping

from ..calculators.upgrade_calculator import UpgradeCalculator
from ..utils.types import JsonValue
from .fields import UpgradeData


class Upgrade:
    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = UpgradeData(data)
        self.stats = UpgradeCalculator(self)
