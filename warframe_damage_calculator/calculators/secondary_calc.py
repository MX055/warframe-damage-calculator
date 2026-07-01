from __future__ import annotations

from ..mechanics import DOT_MULTIPLIERS
from .ranged_calc import RangedCalculator


class SecondaryCalculator(RangedCalculator):

    def calculate_secondary_enervate_bonus(self, initial_crit_chance: float) -> float:
        if self.weapon.effective.secondary_enervate <= 0:
            return 0.0

        reset_after = self.weapon.effective.secondary_enervate
        tolerance = 1e-14
        states = [[1.0] + [0.0] * (reset_after - 1)]
        previous_average = -1.0

        while True:
            current = states[-1]
            stack = len(states) - 1
            cc = initial_crit_chance + 0.1 * stack
            p = min(1.0, max(0.0, cc - 1.0))
            next_state = [0.0] * reset_after

            for big in range(reset_after):
                next_state[big] += current[big] * (1.0 - p)

            for big in range(reset_after - 1):
                next_state[big + 1] += current[big] * p

            states.append(next_state)
            total_probability = 0.0
            average = 0.0

            for stack, probs in enumerate(states):
                weight = sum(probs)
                total_probability += weight
                average += 0.1 * stack * weight

            average /= total_probability
            delta_average = abs(average - previous_average)
            remaining_probability = sum(states[-1])

            if delta_average < tolerance and remaining_probability < tolerance:
                return average

            previous_average = average
    
    def average_secondary_enervate_bonus(self) -> float:
        return self.calculate_secondary_enervate_bonus(self.weapon.moded.crit_chance * self.weapon.moded.multiplicative_crit_chance + self.weapon.moded.flat_crit_chance)
    
    def average_weakpoint_secondary_enervate_bonus(self) -> float:
        return self.calculate_secondary_enervate_bonus(self.weapon.moded.weakpoint_crit_chance * (self.weapon.moded.multiplicative_crit_chance + self.weapon.moded.multiplicative_weakpoint_crit_chance - 1) + self.weapon.moded.flat_crit_chance)
    
    def _flat_dotph_for(self, damage_dist, forced_procs, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        if damage_dist.total_damage <= 0:
            return 0.0
        # Internal bleeding from impact damage
        internal_bleeding_expected_procs = (damage_dist.weight("impact") + forced_procs.get("impact")) * self.weapon.effective.internal_bleeding * self.weapon.effective.status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Regular status procs
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.weapon.effective.status_chance * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2
        # Total DoT damage
        return (dot_damage_per_bullet + internal_bleeding_expected_damage + forced_dot_damage_per_bullet) * (self.weapon.effective.multishot * self.beam_dot_multiplier() if include_multishot else 1)
