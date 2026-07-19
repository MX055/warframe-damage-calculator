from collections.abc import Mapping
from typing import Any

from ..models.data import Data
from ..models.dist import Dist
from ..models.fields import ResolvedStat
from ..models.upgrade import Upgrade
from ..utils.constants import DAMAGE_TYPES


class BuildCalculator:
    BUCKETS = ("static", "conditional", "stacking", "rank_locked", "total")

    def __init__(self, build: Any) -> None:
        self.build = build
        self.static = ResolvedStat()
        self.conditional = ResolvedStat()
        self.stacking = ResolvedStat()
        self.rank_locked = ResolvedStat()
        self.total = ResolvedStat()
        self.resolve()

    @staticmethod
    def _add(stats: Data, stat: str, value: Any) -> None:
        if stat in DAMAGE_TYPES:
            stat, value = "damage", {stat: value}
        current = stats.get(stat)
        if stat == "damage":
            stats[stat] = Dist(current) + Dist(value)
        elif current is None:
            stats[stat] = value
        elif isinstance(value, bool):
            stats[stat] = current or value
        elif isinstance(current, Mapping) and isinstance(value, Mapping):
            stats[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in dict(current) | dict(value)}
        else:
            stats[stat] = current + value

    def resolve(self, weapon: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        names = {" ".join(str(upgrade.context.get("name", "")).casefold().split()) for upgrade in self.build.data.get("upgrades", [])}
        self.build.data.context.sacrificial_set = {"sacrificial pressure", "sacrificial steel"}.issubset(names)
        for bucket in self.BUCKETS:
            setattr(self, bucket, ResolvedStat())

        for upgrade_data in self.build.data.get("upgrades", []):
            calculator = Upgrade(upgrade_data).stats
            calculator.resolve(weapon_data, self.build)
            for bucket in self.BUCKETS:
                target = getattr(self, bucket)
                for stat, value in getattr(calculator, bucket).items():
                    self._add(target, stat, value)
