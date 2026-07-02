from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Weapon


class WeaponFormatter:
    def __init__(self, weapon: Weapon) -> None:
        self.weapon: Weapon = weapon

    def summary(self) -> str:
        raise NotImplementedError
