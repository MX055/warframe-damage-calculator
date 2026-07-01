from dataclasses import dataclass, field, fields

from ..mechanics import dist
from .upgrade import Upgrade


@dataclass(init=False)
class Build(Upgrade):
    upgrades: list[Upgrade] = field(default_factory=list)

    def __init__(self, *upgrades: Upgrade):
        self.upgrades = list(upgrades)

        for stat in fields(Upgrade):
            default_value = stat.default
            values = [getattr(upgrade, stat.name) for upgrade in upgrades]

            if not values:
                setattr(self, stat.name, default_value)
                continue

            if isinstance(default_value, bool):
                setattr(self, stat.name, any(values))
                continue

            if isinstance(default_value, dist):
                setattr(self, stat.name, sum(values, dist()))
                continue

            if isinstance(default_value, (int, float)):
                setattr(self, stat.name, sum(values))
                continue

            setattr(self, stat.name, default_value)
