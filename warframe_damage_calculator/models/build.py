from dataclasses import MISSING, dataclass, fields

from .dist import dist
from .upgrade import Upgrade


@dataclass(init=False)
class Build(Upgrade):
    """Represents a group of upgrades applied together.

    Pass one or more ``Upgrade`` objects to create the final set of bonuses
    for a weapon. A build exposes the same fields as ``Upgrade``, but each
    field contains the combined result.

    Numeric bonuses are added together, damage distributions are merged, and
    boolean options become true if any upgrade enables them. With no upgrades,
    the build keeps the default values.

    Pass a ``Build`` to ``Weapon.configure`` to update a weapon's calculated
    stats.
    """
    def __init__(self, *upgrades: Upgrade) -> None:
        if any(not isinstance(upgrade, Upgrade) for upgrade in upgrades):
            raise TypeError
        self.upgrades = list(upgrades)

        for stat in fields(Upgrade):
            if stat.default_factory is not MISSING:
                default_value = stat.default_factory()
            else:
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
