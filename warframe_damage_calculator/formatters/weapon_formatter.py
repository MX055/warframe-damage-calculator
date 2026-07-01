from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..calculators.weapon_calc import WeaponCalculator
    from ..weapon_models.weapon import Weapon


class WeaponFormatter:
    def __init__(self, weapon: Weapon, calculator: WeaponCalculator) -> None:
        self.weapon = weapon
        self.calc = calculator

    def summary(self) -> str:
        raise NotImplementedError
