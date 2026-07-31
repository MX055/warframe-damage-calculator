from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from .damage import BASE_ELEMENT_TYPES
from .perks import Perk
from .upgrades import Arcane, Mod, Upgrade


class Progenitor:
    __slots__ = ("element", "bonus")

    def __init__(self, element: str, bonus: float) -> None:
        normalized = element.strip().lower()
        allowed = BASE_ELEMENT_TYPES | {"impact", "magnetic", "radiation"}
        if normalized not in allowed: raise ValueError(f"unsupported progenitor element {element!r}")
        value = float(bonus)
        if not 0 <= value <= 0.6: raise ValueError("progenitor bonus must be between 0 and 0.6")
        self.element = normalized
        self.bonus = value

    def __repr__(self) -> str:
        return f"Progenitor(element={self.element!r}, bonus={self.bonus!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Progenitor) and (self.element, self.bonus) == (other.element, other.bonus)

    def __hash__(self) -> int:
        return hash((self.element, self.bonus))


class Loadout:
    __slots__ = ("upgrades", "evolutions", "progenitor")

    def __init__(self, *, upgrades: Iterable[Upgrade] | None = None, evolutions: Iterable[Perk] | None = None, progenitor: Progenitor | None = None) -> None:
        supplied_upgrades = list(upgrades or ())
        supplied_perks = list(evolutions or ())
        if any(not isinstance(upgrade, (Mod, Arcane)) for upgrade in supplied_upgrades): raise TypeError("upgrades must contain Mod or Arcane objects")
        if any(not isinstance(perk, Perk) for perk in supplied_perks): raise TypeError("evolutions must contain Perk objects")
        self.upgrades = [upgrade.copy() for upgrade in supplied_upgrades]
        self.evolutions = supplied_perks
        if progenitor is not None and not isinstance(progenitor, Progenitor): raise TypeError("progenitor must be a Progenitor object")
        self.progenitor = progenitor
        if len(set(self.evolutions)) != len(self.evolutions): raise ValueError("loadout contains duplicate evolution perks")

    def __len__(self) -> int:
        return len(self.upgrades) + len(self.evolutions)

    def __add__(self, other: Upgrade | Loadout) -> Loadout:
        if isinstance(other, Loadout): return Loadout(upgrades=[*self.upgrades, *other.upgrades], evolutions=[*self.evolutions, *other.evolutions], progenitor=other.progenitor or self.progenitor)
        if isinstance(other, Perk): return Loadout(upgrades=self.upgrades, evolutions=[*self.evolutions, other], progenitor=self.progenitor)
        if isinstance(other, (Mod, Arcane)): return Loadout(upgrades=[*self.upgrades, other], evolutions=self.evolutions, progenitor=self.progenitor)
        return NotImplemented

    def __sub__(self, other: Upgrade | Loadout) -> Loadout:
        upgrades = set(other.upgrades if isinstance(other, Loadout) else [other] if isinstance(other, (Mod, Arcane)) else ())
        evolutions = set(other.evolutions if isinstance(other, Loadout) else [other] if isinstance(other, Perk) else ())
        if not isinstance(other, (Mod, Arcane, Perk, Loadout)): return NotImplemented
        return Loadout(upgrades=[upgrade for upgrade in self.upgrades if upgrade not in upgrades], evolutions=[perk for perk in self.evolutions if perk not in evolutions], progenitor=self.progenitor)

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
        return Loadout(upgrades=self.upgrades, evolutions=self.evolutions, progenitor=self.progenitor)
