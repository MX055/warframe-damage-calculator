from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from .damage import BASE_ELEMENT_TYPES
from .upgrades import Perk
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
    __slots__ = ("mods", "arcanes", "evolutions", "progenitor")

    def __init__(self, *, mods: Iterable[Mod] | None = None, arcanes: Iterable[Arcane] | None = None, evolutions: Iterable[Perk] | None = None, progenitor: Progenitor | None = None) -> None:
        supplied_mods = list(mods or ())
        supplied_arcanes = list(arcanes or ())
        supplied_perks = list(evolutions or ())
        if any(not isinstance(mod, Mod) for mod in supplied_mods): raise TypeError("mods must contain Mod objects")
        if any(not isinstance(arcane, Arcane) for arcane in supplied_arcanes): raise TypeError("arcanes must contain Arcane objects")
        if any(not isinstance(perk, Perk) for perk in supplied_perks): raise TypeError("evolutions must contain Perk objects")
        self.mods = [mod.copy() for mod in supplied_mods]
        self.arcanes = [arcane.copy() for arcane in supplied_arcanes]
        self.evolutions = supplied_perks
        if progenitor is not None and not isinstance(progenitor, Progenitor): raise TypeError("progenitor must be a Progenitor object")
        self.progenitor = progenitor
        if len(set(self.evolutions)) != len(self.evolutions): raise ValueError("loadout contains duplicate evolution perks")

    @property
    def upgrades(self) -> tuple[Upgrade, ...]:
        return (*self.mods, *self.arcanes, *self.evolutions)

    @property
    def ranked_upgrades(self) -> tuple[Mod | Arcane, ...]:
        return (*self.mods, *self.arcanes)

    def __len__(self) -> int:
        return len(self.mods) + len(self.arcanes) + len(self.evolutions)

    def __add__(self, other: Upgrade | Loadout) -> Loadout:
        if isinstance(other, Loadout): return Loadout(mods=[*self.mods, *other.mods], arcanes=[*self.arcanes, *other.arcanes], evolutions=[*self.evolutions, *other.evolutions], progenitor=other.progenitor or self.progenitor)
        if isinstance(other, Perk): return Loadout(mods=self.mods, arcanes=self.arcanes, evolutions=[*self.evolutions, other], progenitor=self.progenitor)
        if isinstance(other, Mod): return Loadout(mods=[*self.mods, other], arcanes=self.arcanes, evolutions=self.evolutions, progenitor=self.progenitor)
        if isinstance(other, Arcane): return Loadout(mods=self.mods, arcanes=[*self.arcanes, other], evolutions=self.evolutions, progenitor=self.progenitor)
        return NotImplemented

    def __sub__(self, other: Upgrade | Loadout) -> Loadout:
        if not isinstance(other, (Mod, Arcane, Perk, Loadout)): return NotImplemented
        mods = set(other.mods if isinstance(other, Loadout) else [other] if isinstance(other, Mod) else ())
        arcanes = set(other.arcanes if isinstance(other, Loadout) else [other] if isinstance(other, Arcane) else ())
        evolutions = set(other.evolutions if isinstance(other, Loadout) else [other] if isinstance(other, Perk) else ())
        return Loadout(mods=[mod for mod in self.mods if mod not in mods], arcanes=[arcane for arcane in self.arcanes if arcane not in arcanes], evolutions=[perk for perk in self.evolutions if perk not in evolutions], progenitor=self.progenitor)

    def set(self, **values: object) -> Self:
        consumed: set[str] = set()
        for upgrade in self.ranked_upgrades:
            accepted = ({"rank"} | set(upgrade.stats.manual_fields)) & values.keys()
            if accepted:
                upgrade.set(**{key: values[key] for key in accepted})
                consumed.update(accepted)
        unknown = set(values) - consumed
        if unknown: raise TypeError(f"loadout cannot consume runtime fields: {', '.join(sorted(unknown))}")
        return self

    @classmethod
    def _from_parts(cls, *, mods: Iterable[Mod] = (), arcanes: Iterable[Arcane] = (), evolutions: Iterable[Perk] = (), progenitor: Progenitor | None = None) -> Loadout:
        loadout = cls.__new__(cls)
        loadout.mods = list(mods)
        loadout.arcanes = list(arcanes)
        loadout.evolutions = list(evolutions)
        loadout.progenitor = progenitor
        return loadout

    def copy(self) -> Loadout:
        return Loadout(mods=self.mods, arcanes=self.arcanes, evolutions=self.evolutions, progenitor=self.progenitor)
