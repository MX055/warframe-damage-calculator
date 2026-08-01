from __future__ import annotations

from collections.abc import Mapping

from ..domain.enemies import Enemy
from ..domain.loadouts import Loadout
from ..domain.perks import ResolvedPerk
from ..domain.weapons import Weapon


class CalculationState:
    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, object]) -> None:
        self._values = dict(values)

    def __getattr__(self, name: str) -> object:
        try: return self._values[name]
        except KeyError: raise AttributeError(name) from None

    def as_dict(self) -> dict[str, object]:
        return dict(self._values)


class CalculationContext:
    __slots__ = ("weapon", "target", "attack", "loadout", "resolved_perks", "state")

    def __init__(self, *, weapon: Weapon, target: Enemy, attack: str, loadout: Loadout, resolved_perks: tuple[ResolvedPerk, ...], state: Mapping[str, object]) -> None:
        self.weapon = weapon
        self.target = target
        self.attack = attack
        self.loadout = loadout
        self.resolved_perks = resolved_perks
        self.state = CalculationState(state)
