from __future__ import annotations

from ..calculators import WeaponCalculator
from ..models.build import Build
from ..states.weapon import WeaponState


class WeaponFormatter[TWeaponState: WeaponState]:
    def __init__(self, calculator: WeaponCalculator[TWeaponState]) -> None:
        self.calculator: WeaponCalculator[TWeaponState] = calculator

    def summary(self) -> str:
        raise NotImplementedError
