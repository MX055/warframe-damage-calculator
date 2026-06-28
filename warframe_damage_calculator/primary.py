from __future__ import annotations

from dataclasses import dataclass

from .constants import DOT_MULTIPLIERS
from .dist import Dist
from .ranged import Ranged


@dataclass
class Primary(Ranged):

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded_hunter_munitions = self.config.hunter_munitions
        self.moded_primed_chamber = self.config.primed_chamber
        self.moded_vigilante_bonus = self.config.vigilante_bonus

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective_hunter_munitions = self.moded_hunter_munitions
        self.effective_primed_chamber = self.moded_primed_chamber
        self.effective_vigilante_bonus = self.moded_vigilante_bonus
        self.effective_crit_chance += self.effective_vigilante_bonus
        self.effective_weakpoint_crit_chance += self.effective_vigilante_bonus

    def average_primed_chamber_multiplier(self) -> float:
        return 1 + self.effective_primed_chamber / self.effective_magazine_capacity

    def flat_dph(self) -> float:
        return super().flat_dph() * self.average_primed_chamber_multiplier()

    def flat_weakpoint_dph(self) -> float:
        return super().flat_weakpoint_dph() * self.average_primed_chamber_multiplier()

    def flat_dotph_for(self, damage_dist: Dist, forced_procs: Dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        if damage_dist.total_damage <= 0:
            return 0.0
        average_primed_chamber_multiplier = self.average_primed_chamber_multiplier()
        # Hunter munitions
        hunter_munitions_expected_procs = self.effective_hunter_munitions * min(crit_chance, 1)
        hunter_munitions_damage_per_proc = 2.1 * damage_dist.total_damage * max(self.effective_crit_damage, crit_multiplier) * self.effective_status_damage * self.effective_faction_damage**2 * average_primed_chamber_multiplier
        hunter_munitions_expected_damage = hunter_munitions_expected_procs * hunter_munitions_damage_per_proc
        # Overlap variables
        impact_internal_bleeding = (damage_dist.weight("impact") + forced_procs.get("impact")) * self.effective_internal_bleeding
        guaranteed_proc = int(self.effective_status_chance)
        fractional_proc = self.effective_status_chance % 1
        # Internal bleeding
        internal_bleeding_expected_procs = impact_internal_bleeding * self.effective_status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.effective_status_damage * self.effective_faction_damage**2 * average_primed_chamber_multiplier
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Hunter munitions & Internal bleeding overlap
        prob_at_least_one_internal_bleeding_proc = 1 - (1 - impact_internal_bleeding) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_internal_bleeding))
        overlap_expected_damage = hunter_munitions_expected_procs * prob_at_least_one_internal_bleeding_proc * min(hunter_munitions_damage_per_proc, internal_bleeding_damage_per_proc)
        # Damage per bullet
        extra_slash_damage_per_bullet = hunter_munitions_expected_damage + internal_bleeding_expected_damage - overlap_expected_damage
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective_status_chance * crit_multiplier * self.effective_status_damage * self.effective_faction_damage**2 * average_primed_chamber_multiplier
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.effective_status_damage * self.effective_faction_damage**2 * average_primed_chamber_multiplier
        # Total dot damage
        return (dot_damage_per_bullet + extra_slash_damage_per_bullet + forced_dot_damage_per_bullet) * (self.effective_multishot * self.beam_dot_multiplier() if include_multishot else 1)