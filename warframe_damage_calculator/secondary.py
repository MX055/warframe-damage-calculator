from __future__ import annotations

from dataclasses import dataclass

from .constants import DOT_MULTIPLIERS
from .dist import Dist
from .ranged import Ranged


@dataclass
class Secondary(Ranged):

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded_secondary_enervate = self.config.secondary_enervate

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective_secondary_enervate = self.moded_secondary_enervate
        self.effective_crit_chance += self.average_secondary_enervate_bonus()
        self.effective_weakpoint_crit_chance += self.average_weakpoint_secondary_enervate_bonus()

    def _calculate_secondary_enervate_bonus(self, initial_crit_chance: float) -> float:
        if self.effective_secondary_enervate <= 0:
            return 0.0

        reset_after = self.effective_secondary_enervate
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
        return self._calculate_secondary_enervate_bonus(self.moded_crit_chance * self.moded_multiplicative_crit_chance + self.moded_flat_crit_chance)

    def average_weakpoint_secondary_enervate_bonus(self) -> float:
        return self._calculate_secondary_enervate_bonus(self.moded_weakpoint_crit_chance * (self.moded_multiplicative_crit_chance + self.moded_multiplicative_weakpoint_crit_chance - 1) + self.moded_flat_crit_chance)

    def flat_dotph_for(self, damage_dist: Dist, forced_procs: Dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        if damage_dist.total_damage <= 0:
            return 0.0
        # Internal bleeding
        internal_bleeding_expected_procs = (damage_dist.weight("impact") + forced_procs.get("impact")) * self.effective_internal_bleeding * self.effective_status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.effective_status_damage * self.effective_faction_damage**2
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Damage per bullet
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective_status_chance * crit_multiplier * self.effective_status_damage * self.effective_faction_damage**2
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.effective_status_damage * self.effective_faction_damage**2
        # Total dot damage
        return (dot_damage_per_bullet + internal_bleeding_expected_damage + forced_dot_damage_per_bullet) * (self.effective_multishot * self.beam_dot_multiplier() if include_multishot else 1)
