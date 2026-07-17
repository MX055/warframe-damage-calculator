from functools import cached_property

from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp
from ..models.dist import Dist
from .ranged_calculator import RangedCalculator


class PrimaryCalculator(RangedCalculator):
    DEFAULT_STATS = RangedCalculator.DEFAULT_STATS
    CALCULATED_STATS = RangedCalculator.CALCULATED_STATS | {"hunter_munitions": 0.0, "primed_chamber": 0.0, "vigilante_bonus": 0.0}

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.fire_rate = max(self.base.fire_rate * (1 if self._get("fire_rate_lock", False) else (1 + self._get("fire_rate"))), 0.05)
        self.moded.hunter_munitions = clamp(self._get("hunter_munitions"), 0, 0.3)
        self.moded.primed_chamber = clamp(self._get("primed_chamber"), 0, 1.4)
        self.moded.vigilante_bonus = clamp(self._get("vigilante_bonus"), 0, 0.3)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.hunter_munitions = self.moded.hunter_munitions
        self.effective.primed_chamber = self.moded.primed_chamber
        self.effective.vigilante_bonus = self.moded.vigilante_bonus
        self.effective.crit_chance += self.effective.vigilante_bonus
        self.effective.weakpoint_crit_chance += self.effective.vigilante_bonus

    def _flat_dotph_for(self, damage: Dist, forced_procs: Dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        if damage.total_damage() <= 0:
            return 0.0
        average_primed_chamber_multiplier = self.average_primed_chamber_multiplier
        # Hunter munitions: bleed on crit
        hunter_munitions_expected_procs = self.effective.hunter_munitions * min(crit_chance, 1)
        hunter_munitions_damage_per_proc = 2.1 * damage.total_damage() * max(self.effective.crit_damage, crit_multiplier) * self.effective.status_damage * self.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        hunter_munitions_expected_damage = hunter_munitions_expected_procs * hunter_munitions_damage_per_proc
        # Overlap variables for proc calculation
        impact_internal_bleeding = (damage.weight("impact") + forced_procs.get("impact")) * self.effective.internal_bleeding
        guaranteed_proc, fractional_proc = divmod(self.effective.status_chance, 1)
        # Internal bleeding: armor-ignoring bleed from impact
        internal_bleeding_expected_procs = impact_internal_bleeding * self.effective.status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage.total_damage() * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Avoid double-counting: probability both procs occur on same shot
        prob_at_least_one_internal_bleeding_proc = 1 - (1 - impact_internal_bleeding) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_internal_bleeding))
        overlap_expected_damage = hunter_munitions_expected_procs * prob_at_least_one_internal_bleeding_proc * min(hunter_munitions_damage_per_proc, internal_bleeding_damage_per_proc)
        # Base DoT from regular status procs
        extra_slash_damage_per_bullet = hunter_munitions_expected_damage + internal_bleeding_expected_damage - overlap_expected_damage
        dot_damage_per_bullet = sum(multiplier * damage.get(damage_type) * damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * self.effective.status_chance * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        forced_dot_damage_per_bullet = sum(multiplier * forced_procs.get(damage_type) * damage.get(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * crit_multiplier * self.effective.status_damage * self.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        # Total DoT damage, multiplied by multishot if applicable
        return (dot_damage_per_bullet + extra_slash_damage_per_bullet + forced_dot_damage_per_bullet) * (self.effective.multishot * self.beam_dot_multiplier if include_multishot else 1)

    @cached_property
    def average_primed_chamber_multiplier(self) -> float:
        return 1 + self.effective.primed_chamber / self.effective.magazine_capacity

    @cached_property
    def flat_dph(self) -> float:
        return super().flat_dph * self.average_primed_chamber_multiplier

    @cached_property
    def flat_weakpoint_dph(self) -> float:
        return super().flat_weakpoint_dph * self.average_primed_chamber_multiplier
