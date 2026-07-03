from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from ..utils import DOT_MULTIPLIERS
from .ranged_calculator import RangedCalculator

if TYPE_CHECKING:
    from ..models import Primary


class PrimaryCalculator(RangedCalculator):
    def __init__(self, weapon: Primary) -> None:
        self.weapon: Primary = weapon

    @cached_property
    def average_primed_chamber_multiplier(self) -> float:
        return 1 + self.weapon.effective.primed_chamber / self.weapon.effective.magazine_capacity

    @cached_property
    def flat_dph(self) -> float:
        return super().flat_dph * self.average_primed_chamber_multiplier

    @cached_property
    def flat_weakpoint_dph(self) -> float:
        return super().flat_weakpoint_dph * self.average_primed_chamber_multiplier
    
    def _flat_dotph_for(self, damage_dist, forced_procs, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        if damage_dist.total_damage <= 0:
            return 0.0
        average_primed_chamber_multiplier = self.average_primed_chamber_multiplier
        # Hunter munitions: bleed on crit
        hunter_munitions_expected_procs = self.weapon.effective.hunter_munitions * min(crit_chance, 1)
        hunter_munitions_damage_per_proc = 2.1 * damage_dist.total_damage * max(self.weapon.effective.crit_damage, crit_multiplier) * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        hunter_munitions_expected_damage = hunter_munitions_expected_procs * hunter_munitions_damage_per_proc
        # Overlap variables for proc calculation
        impact_internal_bleeding = (damage_dist.weight("impact") + forced_procs.get("impact")) * self.weapon.effective.internal_bleeding
        guaranteed_proc, fractional_proc = divmod(self.weapon.effective.status_chance, 1)
        # Internal bleeding: armor-ignoring bleed from impact
        internal_bleeding_expected_procs = impact_internal_bleeding * self.weapon.effective.status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Avoid double-counting: probability both procs occur on same shot
        prob_at_least_one_internal_bleeding_proc = 1 - (1 - impact_internal_bleeding) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_internal_bleeding))
        overlap_expected_damage = hunter_munitions_expected_procs * prob_at_least_one_internal_bleeding_proc * min(hunter_munitions_damage_per_proc, internal_bleeding_damage_per_proc)
        # Base DoT from regular status procs
        extra_slash_damage_per_bullet = hunter_munitions_expected_damage + internal_bleeding_expected_damage - overlap_expected_damage
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.weapon.effective.status_chance * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.weapon.effective.status_damage * self.weapon.effective.faction_damage ** 2 * average_primed_chamber_multiplier
        # Total DoT damage, multiplied by multishot if applicable
        return (dot_damage_per_bullet + extra_slash_damage_per_bullet + forced_dot_damage_per_bullet) * (self.weapon.effective.multishot * self.beam_dot_multiplier if include_multishot else 1)
