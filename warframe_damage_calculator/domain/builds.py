from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from .damage import BASE_ELEMENT_TYPES
from .perks import Perk
from .upgrades import Arcane, Mod, Upgrade


class Progenitor:
    __slots__ = ("element", "bonus")

    def __init__(self, *, element: str, bonus: float) -> None:
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


class Build:
    __slots__ = ("mods", "arcanes", "perks", "progenitor")

    def __init__(self, *, mods: Iterable[Mod] | None = None, arcanes: Iterable[Arcane] | None = None, perks: Iterable[Perk] | None = None, progenitor: Progenitor | None = None) -> None:
        supplied_mods = list(mods or ())
        supplied_arcanes = list(arcanes or ())
        supplied_perks = list(perks or ())
        if any(not isinstance(mod, Mod) for mod in supplied_mods): raise TypeError("mods must contain Mod objects")
        if any(not isinstance(arcane, Arcane) for arcane in supplied_arcanes): raise TypeError("arcanes must contain Arcane objects")
        if any(not isinstance(perk, Perk) for perk in supplied_perks): raise TypeError("perks must contain Perk objects")
        self.mods = [mod.copy() for mod in supplied_mods]
        self.arcanes = [arcane.copy() for arcane in supplied_arcanes]
        self.perks = [perk.copy() for perk in supplied_perks]
        if progenitor is not None and not isinstance(progenitor, Progenitor): raise TypeError("progenitor must be a Progenitor object")
        self.progenitor = progenitor
        if len(set(self.perks)) != len(self.perks): raise ValueError("build contains duplicate perks")

    @property
    def upgrades(self) -> tuple[Upgrade, ...]:
        return (*self.mods, *self.arcanes, *self.perks)

    @property
    def ranked_upgrades(self) -> tuple[Mod | Arcane, ...]:
        return (*self.mods, *self.arcanes)

    def __len__(self) -> int:
        return len(self.mods) + len(self.arcanes) + len(self.perks)

    def __add__(self, other: Upgrade | Build) -> Build:
        if isinstance(other, Build): return Build(mods=[*self.mods, *other.mods], arcanes=[*self.arcanes, *other.arcanes], perks=[*self.perks, *other.perks], progenitor=other.progenitor or self.progenitor)
        if isinstance(other, Perk): return Build(mods=self.mods, arcanes=self.arcanes, perks=[*self.perks, other], progenitor=self.progenitor)
        if isinstance(other, Mod): return Build(mods=[*self.mods, other], arcanes=self.arcanes, perks=self.perks, progenitor=self.progenitor)
        if isinstance(other, Arcane): return Build(mods=self.mods, arcanes=[*self.arcanes, other], perks=self.perks, progenitor=self.progenitor)
        return NotImplemented

    def __sub__(self, other: Upgrade | Build) -> Build:
        if not isinstance(other, (Mod, Arcane, Perk, Build)): return NotImplemented
        mods = set(other.mods if isinstance(other, Build) else [other] if isinstance(other, Mod) else ())
        arcanes = set(other.arcanes if isinstance(other, Build) else [other] if isinstance(other, Arcane) else ())
        perks = set(other.perks if isinstance(other, Build) else [other] if isinstance(other, Perk) else ())
        return Build(mods=[mod for mod in self.mods if mod not in mods], arcanes=[arcane for arcane in self.arcanes if arcane not in arcanes], perks=[perk for perk in self.perks if perk not in perks], progenitor=self.progenitor)

    def set(self, **values: object) -> Self:
        consumed: set[str] = set()
        for upgrade in self.ranked_upgrades:
            accepted = ({"rank"} | set(upgrade.stats.manual_fields)) & values.keys()
            if accepted:
                upgrade.set(**{key: values[key] for key in accepted})
                consumed.update(accepted)
        perk_keys = set(values) - consumed
        if perk_keys and self.perks:
            for perk in self.perks:
                perk.set(**{key: values[key] for key in perk_keys})
            consumed.update(perk_keys)
        unknown = set(values) - consumed
        if unknown: raise TypeError(f"build cannot consume runtime fields: {', '.join(sorted(unknown))}")
        return self

    @classmethod
    def _from_parts(cls, *, mods: Iterable[Mod] = (), arcanes: Iterable[Arcane] = (), perks: Iterable[Perk] = (), progenitor: Progenitor | None = None) -> Build:
        build = cls.__new__(cls)
        build.mods = list(mods)
        build.arcanes = list(arcanes)
        build.perks = list(perks)
        build.progenitor = progenitor
        return build

    def copy(self) -> Build:
        return Build(mods=self.mods, arcanes=self.arcanes, perks=self.perks, progenitor=self.progenitor)
