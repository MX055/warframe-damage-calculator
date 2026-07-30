from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from .perks import Perk
from .upgrades import Upgrade


class Loadout:
    __slots__ = ("upgrades", "evolutions")

    def __init__(self, *, upgrades: Iterable[Upgrade] | None = None, evolutions: Iterable[Perk] | None = None) -> None:
        supplied_upgrades = list(upgrades or ())
        supplied_perks = list(evolutions or ())
        if any(not isinstance(upgrade, Upgrade) for upgrade in supplied_upgrades): raise TypeError("upgrades must contain Upgrade objects")
        if any(not isinstance(perk, Perk) for perk in supplied_perks): raise TypeError("evolutions must contain Perk objects")
        self.upgrades = [upgrade.copy() for upgrade in supplied_upgrades]
        self.evolutions = supplied_perks
        if len(set(self.evolutions)) != len(self.evolutions): raise ValueError("loadout contains duplicate evolution perks")

    def __len__(self) -> int:
        return len(self.upgrades) + len(self.evolutions)

    def __add__(self, other: Upgrade | Perk | Loadout) -> Loadout:
        if isinstance(other, Loadout): return Loadout(upgrades=[*self.upgrades, *other.upgrades], evolutions=[*self.evolutions, *other.evolutions])
        if isinstance(other, Upgrade): return Loadout(upgrades=[*self.upgrades, other], evolutions=self.evolutions)
        if isinstance(other, Perk): return Loadout(upgrades=self.upgrades, evolutions=[*self.evolutions, other])
        return NotImplemented

    def __sub__(self, other: Upgrade | Perk | Loadout) -> Loadout:
        upgrades = set(other.upgrades if isinstance(other, Loadout) else [other] if isinstance(other, Upgrade) else ())
        evolutions = set(other.evolutions if isinstance(other, Loadout) else [other] if isinstance(other, Perk) else ())
        if not isinstance(other, (Upgrade, Perk, Loadout)): return NotImplemented
        return Loadout(upgrades=[upgrade for upgrade in self.upgrades if upgrade not in upgrades], evolutions=[perk for perk in self.evolutions if perk not in evolutions])

    def set(self, **values: object) -> Self:
        consumed: set[str] = set()
        for upgrade in self.upgrades:
            accepted = ({"rank"} | set(upgrade.stats.manual_fields)) & values.keys()
            if accepted:
                upgrade.set(**{key: values[key] for key in accepted})
                consumed.update(accepted)
        unknown = set(values) - consumed
        if unknown: raise TypeError(f"loadout cannot consume runtime fields: {', '.join(sorted(unknown))}")
        return self

    def copy(self) -> Loadout:
        return Loadout(upgrades=self.upgrades, evolutions=self.evolutions)
