from __future__ import annotations

from functools import cached_property

from ..utils import DOT_MULTIPLIERS, clamp
from ..states import SecondaryState
from ..models import dist
from .ranged_calculator import RangedCalculator


class SecondaryCalculator(RangedCalculator[SecondaryState]):
    def __init__(self, base: SecondaryState) -> None:
        super().__init__(base)

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.secondary_enervate = clamp(self._upgrade("secondary_enervate"), 0, 6)
        self.moded.secondary_encumber = clamp(self._upgrade("secondary_encumber"), 0, 0.24)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.secondary_enervate = self.moded.secondary_enervate
        self.effective.secondary_encumber = self.moded.secondary_encumber

    def _average_secondary_enervate_bonus_for(self, crit_chance: float, max_stacks: int = 500) -> float:
        R = self.effective.secondary_enervate
        if R == 0:
            return 0.0
        M = max_stacks
        L = [[0.0] * R for _ in range(M + 1)]
        A = [[0.0] * R for _ in range(M + 1)]

        p = max(0.0, min(1.0, crit_chance + 0.1 * M - 1))
        q = 1.0 - p

        if q == 1.0:
            return float("inf")

        L[M][R - 1] = 1.0 / (1.0 - q)
        A[M][R - 1] = M / (1.0 - q)

        for k in range(R - 2, -1, -1):
            L[M][k] = (1.0 + p * L[M][k + 1]) / (1.0 - q)
            A[M][k] = (M + p * A[M][k + 1]) / (1.0 - q)

        for s in range(M - 1, -1, -1):
            p = max(0.0, min(1.0, crit_chance + 0.1 * s - 1))
            q = 1.0 - p
            
            L[s][R - 1] = 1.0 + q * L[s + 1][R - 1]
            A[s][R - 1] = s + q * A[s + 1][R - 1]

            for k in range(R - 2, -1, -1):
                L[s][k] = 1.0 + q * L[s + 1][k] + p * L[s + 1][k + 1]
                A[s][k] = s + q * A[s + 1][k] + p * A[s + 1][k + 1]

        return 0.1 * A[0][0] / L[0][0]

    def _flat_dotph_for(self, damage_dist: dist, forced_procs: dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:  # Secondary Ecumber Calculations Need Testing In-Game
        if damage_dist.total_damage() <= 0:
            return 0.0
        secondary_encumber_chance = 1 - (1 - self.effective.secondary_encumber * min(self.effective.status_chance, 1))**self.effective.multishot
        secondary_encumber_dot = secondary_encumber_chance * damage_dist.total_damage() * 14.1/13 * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2
        # Internal bleeding from impact damage
        internal_bleeding_expected_procs = ((damage_dist.weight("impact") + forced_procs.get("impact")) * self.effective.status_chance + secondary_encumber_chance/13) * self.effective.internal_bleeding
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage() * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Regular status procs
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective.status_chance * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2
        # Total DoT damage
        return (dot_damage_per_bullet + internal_bleeding_expected_damage + forced_dot_damage_per_bullet) * (self.effective.multishot * self.beam_dot_multiplier if include_multishot else 1) + secondary_encumber_dot
    
    @cached_property
    def average_secondary_enervate_bonus(self) -> float:
        return self._average_secondary_enervate_bonus_for(self.moded.crit_chance * self.moded.multiplicative_crit_chance + self.moded.flat_crit_chance)

    @cached_property
    def average_weakpoint_secondary_enervate_bonus(self) -> float:
        return self._average_secondary_enervate_bonus_for(self.moded.weakpoint_crit_chance * (self.moded.multiplicative_crit_chance + self.moded.multiplicative_weakpoint_crit_chance - 1) + self.moded.flat_crit_chance)

    @cached_property
    def average_crit_chance(self) -> float:
        return self.effective.crit_chance + self.average_secondary_enervate_bonus

    @cached_property
    def average_weakpoint_crit_chance(self) -> float:
        return self.effective.weakpoint_crit_chance + self.average_weakpoint_secondary_enervate_bonus
