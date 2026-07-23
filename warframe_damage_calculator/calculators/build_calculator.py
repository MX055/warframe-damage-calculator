from typing import Any

from ..fields.upgrade import ResolvedStat
from ..models.data import Data
from .upgrade_calculator import UpgradeCalculator


class BuildCalculator(UpgradeCalculator):
    BUCKETS = ("static", "conditional", "modular", "stacking", "rank_locked", "total")

    def __init__(self, build: Any) -> None:
        self.build = build
        self.resolve()

    def resolve(self, weapon: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = Data({
            "equipped": [" ".join(str(upgrade.data.name or "").casefold().split()) for upgrade in self.build.upgrades]
        })
        for bucket in self.BUCKETS:
            setattr(self, bucket, ResolvedStat())

        for upgrade in self.build.upgrades:
            calculator = upgrade.stats
            calculator.resolve(weapon_data, build_data)
            for bucket in self.BUCKETS:
                target = getattr(self, bucket)
                for stat, value in getattr(calculator, bucket).items():
                    self._merge_stat(target, stat, value)
