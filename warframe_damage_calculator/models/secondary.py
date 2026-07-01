from __future__ import annotations

from ..mechanics import DOT_MULTIPLIERS, SecondaryState, dist, clamp
from .ranged import Ranged


class Secondary(Ranged[SecondaryState]):
    def __init__(self, damage_dist: dist | None = None, forced_procs: dist | None = None, explosion_damage_dist: dist | None = None, explosion_forced_procs: dist | None = None, crit_chance: float = 0.0, crit_damage: float = 0.0, status_chance: float = 0.0, weakpoint_damage: float = 3.0, fire_rate: float = 0.0, charge_time: float = 0.0, reload_speed: float = 0.0, magazine_capacity: int = 1, multishot: float = 1.0, is_beam: bool = False) -> None:
        super().__init__(SecondaryState(damage_dist=damage_dist or dist(), forced_procs=forced_procs or dist(), crit_chance=crit_chance, crit_damage=crit_damage, status_chance=status_chance, explosion_damage_dist=explosion_damage_dist or dist(), explosion_forced_procs=explosion_forced_procs or dist(), weakpoint_damage=weakpoint_damage, fire_rate=fire_rate, charge_time=charge_time, reload_speed=reload_speed, magazine_capacity=magazine_capacity, multishot=multishot, is_beam=is_beam))

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.secondary_enervate = clamp(self.config.secondary_enervate, 1, 6)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.secondary_enervate = self.moded.secondary_enervate
        self.effective.crit_chance += self.average_secondary_enervate_bonus()
        self.effective.weakpoint_crit_chance += self.average_weakpoint_secondary_enervate_bonus()

    def _calculate_secondary_enervate_bonus(self, initial_crit_chance: float) -> float:
        if self.effective.secondary_enervate <= 0:
            return 0.0

        reset_after = self.effective.secondary_enervate
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
        return self._calculate_secondary_enervate_bonus(self.moded.crit_chance * self.moded.multiplicative_crit_chance + self.moded.flat_crit_chance)

    def average_weakpoint_secondary_enervate_bonus(self) -> float:
        return self._calculate_secondary_enervate_bonus(self.moded.weakpoint_crit_chance * (self.moded.multiplicative_crit_chance + self.moded.multiplicative_weakpoint_crit_chance - 1) + self.moded.flat_crit_chance)

    def flat_dotph_for(self, damage_dist: dist, forced_procs: dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        if damage_dist.total_damage <= 0:
            return 0.0
        # Internal bleeding
        internal_bleeding_expected_procs = (damage_dist.weight("impact") + forced_procs.get("impact")) * self.effective.internal_bleeding * self.effective.status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Damage per bullet
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective.status_chance * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2
        # Total dot damage
        return (dot_damage_per_bullet + internal_bleeding_expected_damage + forced_dot_damage_per_bullet) * (self.effective.multishot * self.beam_dot_multiplier() if include_multishot else 1)