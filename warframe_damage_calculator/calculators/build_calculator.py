from typing import Any

from ..models.data import Data
from ..models.dist import Dist
from ..models.upgrade import Upgrade
from ..utils.constants import DAMAGE_TYPES


class BuildCalculator:
    BUCKETS = ("static", "conditional", "stacking", "rank_locked", "total")

    def __init__(self, build: Any) -> None:
        self.build = build
        self.static = Data()
        self.conditional = Data()
        self.stacking = Data()
        self.rank_locked = Data()
        self.total = Data()
        self.resolve()

    @staticmethod
    def _add(stats: Data, stat: str, value: Any) -> None:
        if stat in DAMAGE_TYPES:
            stat, value = "damage", {stat: value}
        current = stats.get(stat)
        if current is None:
            stats[stat] = value
        elif isinstance(value, bool):
            stats[stat] = current or value
        elif isinstance(current, dict) and isinstance(value, dict):
            stats[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in current | value}
        else:
            stats[stat] = current + value

    @staticmethod
    def _combine_damage(stats: Data) -> None:
        if "damage" in stats:
            stats.damage = Dist(stats.damage)

    def resolve(self, weapon: Data | object | None = None) -> dict[str, Data]:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        for bucket in self.BUCKETS:
            setattr(self, bucket, Data())

        for upgrade_data in self.build.data.get("upgrades", []):
            calculator = Upgrade(upgrade_data).stats
            calculator.resolve(weapon_data, self.build)
            for bucket in self.BUCKETS:
                target = getattr(self, bucket)
                for stat, value in getattr(calculator, bucket).items():
                    self._add(target, stat, value)

        for bucket in self.BUCKETS:
            self._combine_damage(getattr(self, bucket))
        return {"stats": self.total, "context": Data()}
