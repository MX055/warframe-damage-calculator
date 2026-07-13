from __future__ import annotations

from ..calculators import WeaponCalculator
from ..states import WeaponState


class WeaponFormatter[TWeaponState: WeaponState]:
    def __init__(self, calculator: WeaponCalculator[TWeaponState]) -> None:
        self.calculator: WeaponCalculator[TWeaponState] = calculator

    def summary(self) -> str:
        raise NotImplementedError
    
    def upgrades(self) -> str:
        contributions = self.calculator.contribution_proportions
        max_len = max(len(name) for name in contributions)
        return "\n".join(f"{f'{name}:':<{max_len + 1}} {contribution:.2%}" for name, contribution in contributions.items())

