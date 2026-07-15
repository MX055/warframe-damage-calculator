from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .data import Data
from .upgrade import Upgrade


class Build:
    def __init__(self, *upgrades: Upgrade) -> None:
        self.upgrades = list(upgrades)

    def __iter__(self) -> Iterator[Upgrade]:
        return iter(self.upgrades)
    
    def __add__(self, other: Build | Upgrade) -> Build:
        return Build(*self, other) if isinstance(other, Upgrade) else Build(*self, *other)
    
    def __radd__(self, other: Upgrade) -> Build:
        return Build(other, *self)

    def __sub__(self, other: Build | Upgrade) -> Build:
        excluded = {other} if isinstance(other, Upgrade) else set(other)
        return Build(*(upgrade for upgrade in self if upgrade not in excluded))

    def resolve(self, context: Mapping[str, Any] | None = None) -> Build:
        from ..calculators.upgrade_calculator import UpgradeCalculator

        names = {" ".join((upgrade.context.name or "").casefold().replace("_", " ").replace("-", " ").split()) for upgrade in self}
        context = Data(context)
        weapon = UpgradeCalculator._key(context.get("type") or context.get("weapon") or "")
        types = {weapon, UpgradeCalculator._key(context.get("category") or "")} - {""}
        if weapon == "bow": types.add("rifle")
        context.update({key: key in types for key in UpgradeCalculator.AUTOMATIC - {"sacrificial set"}})
        context.weapon = weapon
        context["sacrificial set"] = {"sacrificial pressure", "sacrificial steel"}.issubset(names)
        upgrades = [upgrade.copy() for upgrade in self]
        for upgrade in upgrades: upgrade.data.context = context | upgrade.context
        return Build(*(upgrade.resolve() for upgrade in upgrades))

    def aggregate(self) -> Data:
        stats = Data()
        for upgrade in self:
            for stat, value in upgrade.stats.items():
                current = stats.get(stat)
                stats[stat] = value if current is None else current or value if isinstance(value, bool) else current + value
        return stats

    def get(self, stat: str, default: Any = 0) -> Any: return self.aggregate().get(stat, default)
