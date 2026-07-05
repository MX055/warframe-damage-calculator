from __future__ import annotations

from functools import cached_property

import numpy as np

from ..utils import DOT_MULTIPLIERS, clamp
from ..states import SecondaryState
from ..models import dist
from .ranged_calculator import RangedCalculator


class SecondaryCalculator(RangedCalculator[SecondaryState]):
    """Calculator for secondary weapons.

    Extends the normal ranged calculations with secondary-only build
    effects.

    Secondary Enervate increases average critical chance based on its stack
    behavior. Secondary Encumber adds expected damage over time and extra
    status-proc interactions.

    Used by ``Secondary`` after a ``Build`` is configured.
    """
    def __init__(self, base: SecondaryState) -> None:
        super().__init__(base)

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.secondary_enervate = clamp(self.build.secondary_enervate, 0, 6)
        self.moded.secondary_encumber = clamp(self.build.secondary_encumber, 0, 0.24)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.secondary_enervate = self.moded.secondary_enervate
        self.effective.secondary_encumber = self.moded.secondary_encumber

    def _average_secondary_enervate_bonus_for(self, crit_chance: float, max_stacks: int = 100) -> float:
        reset_after = self.effective.secondary_enervate
        if reset_after == 0:
            return 0.0
        states = [(s, c) for s in range(max_stacks + 1) for c in range(reset_after)]
        index = {state: i for i, state in enumerate(states)}
        m = len(states)
        P = np.zeros((m, m))

        for s, c in states:
            i = index[(s, c)]
            p = np.clip(crit_chance + 0.1 * s - 1, 0, 1)
            next_stack = min(s + 1, max_stacks)
            P[i, index[(next_stack, c)]] += 1 - p
            crit_target = (0, 0) if c == reset_after - 1 else (next_stack, c + 1)
            P[i, index[crit_target]] += p

        A = P.T - np.eye(m)
        A[-1] = 1
        b = np.zeros(m)
        b[-1] = 1
        pi = np.linalg.solve(A, b)
        stack_bonus = np.array([0.1 * s for s, _ in states])
        return float(pi @ stack_bonus)

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
