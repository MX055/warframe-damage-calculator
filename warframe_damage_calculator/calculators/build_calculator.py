from collections.abc import Mapping
from typing import Any

from ..models.data import Data
from ..models.dist import Dist
from ..models.fields import ResolvedStat
from ..models.upgrade import Upgrade
from ..utils.constants import DAMAGE_TYPES


class BuildCalculator:
    BUCKETS = ("static", "conditional", "modular", "stacking", "rank_locked", "total")

    def __init__(self, build: Any) -> None:
        self.build = build
        self.static = ResolvedStat()
        self.conditional = ResolvedStat()
        self.modular = ResolvedStat()
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
        elif stat == "condition_overload":
            current = current or {}
            maximums = {current.get("max_stacks", 0), value.get("max_stacks", 0)}
            stats[stat] = {
                "value": current.get("value", 0) + value.get("value", 0),
                "max_stacks": "inf" if "inf" in maximums else max(maximums),
            }
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
        self.build.data.context.equipped = [" ".join(str(upgrade.data.name or "").casefold().split()) for upgrade in self.build.upgrades]
        for bucket in self.BUCKETS:
            setattr(self, bucket, ResolvedStat())

        for upgrade in self.build.upgrades:
            calculator = upgrade.stats
            calculator.resolve(weapon_data, self.build)
            for bucket in self.BUCKETS:
                target = getattr(self, bucket)
                for stat, value in getattr(calculator, bucket).items():
                    self._add(target, stat, value)
