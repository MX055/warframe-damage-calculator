from ..fields.upgrade import ResolvedStat
from ..core.data import Data
from ..protocols import BuildOwner
from .stat_aggregation import merge_resolved_stat
from .upgrade_calculator import UpgradeCalculator


class BuildCalculator:
    static: ResolvedStat
    conditional: ResolvedStat
    modular: ResolvedStat
    stacking: ResolvedStat
    rank_locked: ResolvedStat
    total: ResolvedStat

    BUCKETS = UpgradeCalculator.BUCKETS

    def __init__(self, build: BuildOwner) -> None:
        self.build = build
        self.resolve()

    def resolve(self, weapon: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = Data({"equipped": [str(upgrade.data.name or "") for upgrade in self.build.upgrades]})
        for bucket in self.BUCKETS:
            setattr(self, bucket, ResolvedStat())

        for upgrade in self.build.upgrades:
            calculator = upgrade.results
            calculator.resolve(weapon_data, build_data)
            for bucket in self.BUCKETS:
                merge_resolved_stat(getattr(self, bucket), getattr(calculator, bucket))
