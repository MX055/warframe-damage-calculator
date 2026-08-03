from __future__ import annotations

from ..domain.enemies import Enemy
from ..domain.builds import Build
from ..domain.perks import ResolvedPerk
from ..domain.state import State
from ..domain.weapons import Weapon


class CalculationContext:
    __slots__ = ("weapon", "target", "attack", "build", "resolved_perks", "state")

    def __init__(self, *, weapon: Weapon, target: Enemy, attack: str, build: Build, resolved_perks: tuple[ResolvedPerk, ...], state: State) -> None:
        self.weapon = weapon
        self.target = target
        self.attack = attack
        self.build = build
        self.resolved_perks = resolved_perks
        self.state = state
