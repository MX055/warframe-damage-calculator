from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np

from ..utils import DOT_MULTIPLIERS
from .ranged_calculator import RangedCalculator

if TYPE_CHECKING:
    from ..models import Secondary


class SecondaryCalculator(RangedCalculator):
    def __init__(self, weapon: Secondary) -> None:
        self.weapon: Secondary = weapon
    
    @cached_property
    def average_secondary_enervate_bonus(self) -> float:
        return self._average_secondary_enervate_bonus_for(self.weapon.moded.crit_chance * self.weapon.moded.multiplicative_crit_chance + self.weapon.moded.flat_crit_chance)

    @cached_property
    def average_weakpoint_secondary_enervate_bonus(self) -> float:
        return self._average_secondary_enervate_bonus_for(self.weapon.moded.weakpoint_crit_chance * (self.weapon.moded.multiplicative_crit_chance + self.weapon.moded.multiplicative_weakpoint_crit_chance - 1) + self.weapon.moded.flat_crit_chance)

    @cached_property
    def average_crit_chance(self) -> float:
        return self.weapon.effective.crit_chance + self.average_secondary_enervate_bonus

    @cached_property
    def average_weakpoint_crit_chance(self) -> float:
        return self.weapon.effective.weakpoint_crit_chance + self.average_weakpoint_secondary_enervate_bonus
    
    def _average_secondary_enervate_bonus_for(self, crit_chance: float, max_stacks: int = 100) -> float:
        reset_after = self.weapon.effective.secondary_enervate
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

    def _flat_dotph_for(self, damage_dist, forced_procs, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float: # Secondary Ecumber Calculations Need Testing In-Game
        if damage_dist.total_damage <= 0:
            return 0.0
        secondary_encumber_chance = 1 - (1 - self.weapon.effective.secondary_encumber * min(self.weapon.effective.status_chance, 1))**self.weapon.effective.multishot
        secondary_encumber_dot = secondary_encumber_chance * damage_dist.total_damage * 14.1/13 * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage**2
        # Internal bleeding from impact damage
        internal_bleeding_expected_procs = ((damage_dist.weight("impact") + forced_procs.get("impact")) * self.weapon.effective.status_chance + secondary_encumber_chance/13) * self.weapon.effective.internal_bleeding
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Regular status procs
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.weapon.effective.status_chance * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2
        # Total DoT damage
        return (dot_damage_per_bullet + internal_bleeding_expected_damage + forced_dot_damage_per_bullet) * (self.weapon.effective.multishot * self.beam_dot_multiplier if include_multishot else 1) + secondary_encumber_dot
