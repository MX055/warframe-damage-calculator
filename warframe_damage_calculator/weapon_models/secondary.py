from __future__ import annotations

from ..mechanics import SecondaryState, dist, clamp
from ..calculators import SecondaryCalculator
from .ranged import Ranged


class Secondary(Ranged[SecondaryState]):
    _calculator_class = SecondaryCalculator

    def __init__(self, damage_dist: dist | None = None, forced_procs: dist | None = None, explosion_damage_dist: dist | None = None, explosion_forced_procs: dist | None = None, crit_chance: float = 0.0, crit_damage: float = 0.0, status_chance: float = 0.0, weakpoint_damage: float = 3.0, fire_rate: float = 0.0, charge_time: float = 0.0, reload_speed: float = 0.0, magazine_capacity: int = 1, multishot: float = 1.0, is_beam: bool = False) -> None:
        super().__init__(SecondaryState(damage_dist=damage_dist or dist(), forced_procs=forced_procs or dist(), crit_chance=crit_chance, crit_damage=crit_damage, status_chance=status_chance, explosion_damage_dist=explosion_damage_dist or dist(), explosion_forced_procs=explosion_forced_procs or dist(), weakpoint_damage=weakpoint_damage, fire_rate=fire_rate, charge_time=charge_time, reload_speed=reload_speed, magazine_capacity=magazine_capacity, multishot=multishot, is_beam=is_beam))

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.secondary_enervate = clamp(self.build.secondary_enervate, 0, 6)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.secondary_enervate = self.moded.secondary_enervate