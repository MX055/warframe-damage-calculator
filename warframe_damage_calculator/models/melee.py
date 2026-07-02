from __future__ import annotations

from ..calculators import MeleeCalculator
from ..formatters import MeleeFormatter
from ..utils import clamp
from .states import MeleeState
from .dist import dist
from .weapon import Weapon


class Melee(Weapon[MeleeState, MeleeCalculator, MeleeFormatter]):
    calculator_class = MeleeCalculator
    formatter_class = MeleeFormatter

    def __init__(self, damage_dist: dist | None = None, forced_procs: dist | None = None, crit_chance: float = 0.0, crit_damage: float = 0.0, status_chance: float = 0.0, attack_speed: float = 0.0) -> None:
        super().__init__(MeleeState(damage_dist=damage_dist or dist(), forced_procs=forced_procs or dist(), crit_chance=crit_chance, crit_damage=crit_damage, status_chance=status_chance, attack_speed=attack_speed))

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.attack_speed = max(self.base.attack_speed * (1 + self.build.attack_speed), 0)
        self.moded.melee_duplicate = clamp(self.build.melee_duplicate, 0, 1)
        self.moded.melee_doughty = clamp(self.build.melee_doughty, 0, 1)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.attack_speed = self.moded.attack_speed
        self.effective.melee_duplicate = self.moded.melee_duplicate
        self.effective.melee_doughty = self.moded.melee_doughty

        