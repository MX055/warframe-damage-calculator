from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp
from ..models.dist import Dist
from .ranged_calculator import RangedCalculator


class SecondaryCalculator(RangedCalculator):
    def _compute_modded_stats(self) -> None:
        super()._compute_modded_stats()
        build = self.build.stats.total
        
        self.modded.secondary_enervate = clamp(build.secondary_enervate, 0, 6)
        self.modded.secondary_encumber = clamp(build.secondary_encumber, 0, 0.24)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.secondary_enervate = self.modded.secondary_enervate
        self.effective.secondary_encumber = self.modded.secondary_encumber

    def _compute_average_stats(self) -> None:
        super()._compute_average_stats()
        secondary_enervate_bonus = self._average_secondary_enervate_bonus_for(self.modded.crit_chance * self.modded.multiplicative_crit_chance + self.modded.flat_crit_chance)
        weakpoint_secondary_enervate_bonus = self._average_secondary_enervate_bonus_for(self.modded.weakpoint_crit_chance * (self.modded.multiplicative_crit_chance + self.modded.multiplicative_weakpoint_crit_chance - 1) + self.modded.flat_crit_chance)
        related_flat = sum(state.damage.total_damage() * state.multishot * state.faction_damage * (1 + state.crit_chance * (state.crit_damage - 1)) for state in self.related.values())
        related_weakpoint = sum(state.damage.total_damage() * state.multishot * state.faction_damage * state.weakpoint_damage * (1 + state.weakpoint_crit_chance * (state.crit_damage - 1)) for state in self.related.values())

        self.average.secondary_enervate_bonus = secondary_enervate_bonus
        self.average.weakpoint_secondary_enervate_bonus = weakpoint_secondary_enervate_bonus
        self.average.crit_chance = self.effective.crit_chance + secondary_enervate_bonus
        self.average.weakpoint_crit_chance = self.effective.weakpoint_crit_chance + weakpoint_secondary_enervate_bonus
        self.average.crit_multiplier = 1 + self.average.crit_chance * (self.effective.crit_damage - 1)
        self.average.weakpoint_crit_multiplier = 1 + self.average.weakpoint_crit_chance * (self.effective.crit_damage - 1)
        self.average.flat_dph = self.effective.damage.total_damage() * self.effective.multishot * self.effective.faction_damage * self.average.crit_multiplier + related_flat
        self.average.flat_weakpoint_dph = self.effective.damage.total_damage() * self.effective.multishot * self.effective.weakpoint_damage * self.average.weakpoint_crit_multiplier * self.effective.faction_damage + related_weakpoint
        self.average.flat_dps = self.average.fire_rate * self.average.flat_dph
        self.average.flat_weakpoint_dps = self.average.fire_rate * self.average.flat_weakpoint_dph
        self.average.flat_dotph = self._flat_dotph_for(self.effective.damage, self.base.forced_procs, self.average.crit_chance, self.average.crit_multiplier) + self.related_dot
        self.average.flat_weakpoint_dotph = self._flat_dotph_for(self.effective.damage, self.base.forced_procs, self.average.weakpoint_crit_chance, self.average.weakpoint_crit_multiplier) + self.related_dot
        self.average.flat_dotps = self.average.fire_rate * self.average.flat_dotph
        self.average.flat_weakpoint_dotps = self.average.fire_rate * self.average.flat_weakpoint_dotph
        self.average.total_dph = self.average.flat_dph + self.average.flat_dotph
        self.average.total_weakpoint_dph = self.average.flat_weakpoint_dph + self.average.flat_weakpoint_dotph
        self.average.total_dps = self.average.flat_dps + self.average.flat_dotps
        self.average.total_weakpoint_dps = self.average.flat_weakpoint_dps + self.average.flat_weakpoint_dotps

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

    def _flat_dotph_for(self, damage: Dist, forced_procs: Dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:  # Secondary Encumber calculations need testing in-game
        if damage.total_damage() <= 0:
            return 0.0
        secondary_encumber_chance = 1 - (1 - self.effective.secondary_encumber * min(self.effective.status_chance, 1))**self.effective.multishot
        secondary_encumber_dot = secondary_encumber_chance * damage.total_damage() * 14.1/13 * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2
        # Internal bleeding from impact damage
        internal_bleeding_expected_procs = ((damage.weight("impact") + forced_procs.get("impact")) * self.effective.status_chance + secondary_encumber_chance/13) * self.effective.internal_bleeding
        internal_bleeding_damage_per_proc = 2.1 * damage.total_damage() * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Regular status procs
        dot_damage_per_bullet = sum(multiplier * damage.get(damage_type) * damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * self.effective.status_chance * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2
        forced_dot_damage_per_bullet = sum(multiplier * forced_procs.get(damage_type) * damage.get(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2
        # Total DoT damage
        return (dot_damage_per_bullet + internal_bleeding_expected_damage + forced_dot_damage_per_bullet) * (self.effective.multishot * self.average.beam_dot_multiplier if include_multishot else 1) + secondary_encumber_dot
