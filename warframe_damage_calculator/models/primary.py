from __future__ import annotations

from ..mechanics import DOT_MULTIPLIERS, PrimaryState, dist, clamp
from .ranged import Ranged


class Primary(Ranged[PrimaryState]):
    def __init__(self, damage_dist: dist | None = None, forced_procs: dist | None = None, explosion_damage_dist: dist | None = None, explosion_forced_procs: dist | None = None, crit_chance: float = 0.0, crit_damage: float = 0.0, status_chance: float = 0.0, weakpoint_damage: float = 3.0, fire_rate: float = 0.0, charge_time: float = 0.0, reload_speed: float = 0.0, magazine_capacity: int = 1, multishot: float = 1.0, is_beam: bool = False) -> None:
        super().__init__(PrimaryState(damage_dist=damage_dist or dist(), forced_procs=forced_procs or dist(), crit_chance=crit_chance, crit_damage=crit_damage, status_chance=status_chance, explosion_damage_dist=explosion_damage_dist or dist(), explosion_forced_procs=explosion_forced_procs or dist(), weakpoint_damage=weakpoint_damage, fire_rate=fire_rate, charge_time=charge_time, reload_speed=reload_speed, magazine_capacity=magazine_capacity, multishot=multishot, is_beam=is_beam))

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.hunter_munitions = clamp(self.config.hunter_munitions, 0, 0.3)
        self.moded.primed_chamber = clamp(self.config.primed_chamber, 0, 1.4)
        self.moded.vigilante_bonus = clamp(self.config.vigilante_bonus, 0, 0.3)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.hunter_munitions = self.moded.hunter_munitions
        self.effective.primed_chamber = self.moded.primed_chamber
        self.effective.vigilante_bonus = self.moded.vigilante_bonus
        self.effective.crit_chance += self.effective.vigilante_bonus
        self.effective.weakpoint_crit_chance += self.effective.vigilante_bonus

    def average_primed_chamber_multiplier(self) -> float:
        return 1 + self.effective.primed_chamber / self.effective.magazine_capacity

    def flat_dph(self) -> float:
        return super().flat_dph() * self.average_primed_chamber_multiplier()

    def flat_weakpoint_dph(self) -> float:
        return super().flat_weakpoint_dph() * self.average_primed_chamber_multiplier()

    def flat_dotph_for(self, damage_dist: dist, forced_procs: dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float: # Requires In-Game Testing
        if damage_dist.total_damage <= 0:
            return 0.0
        average_primed_chamber_multiplier = self.average_primed_chamber_multiplier()
        # Hunter munitions
        hunter_munitions_expected_procs = self.effective.hunter_munitions * min(crit_chance, 1)
        hunter_munitions_damage_per_proc = 2.1 * damage_dist.total_damage * max(self.effective.crit_damage, crit_multiplier) * self.effective.status_damage * self.effective.faction_damage**2 * average_primed_chamber_multiplier
        hunter_munitions_expected_damage = hunter_munitions_expected_procs * hunter_munitions_damage_per_proc
        # Overlap variables
        impact_internal_bleeding = (damage_dist.weight("impact") + forced_procs.get("impact")) * self.effective.internal_bleeding
        guaranteed_proc = int(self.effective.status_chance)
        fractional_proc = self.effective.status_chance % 1
        # Internal bleeding
        internal_bleeding_expected_procs = impact_internal_bleeding * self.effective.status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2 * average_primed_chamber_multiplier
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Hunter munitions & Internal bleeding overlap
        prob_at_least_one_internal_bleeding_proc = 1 - (1 - impact_internal_bleeding) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_internal_bleeding))
        overlap_expected_damage = hunter_munitions_expected_procs * prob_at_least_one_internal_bleeding_proc * min(hunter_munitions_damage_per_proc, internal_bleeding_damage_per_proc)
        # Damage per bullet
        extra_slash_damage_per_bullet = hunter_munitions_expected_damage + internal_bleeding_expected_damage - overlap_expected_damage
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective.status_chance * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2 * average_primed_chamber_multiplier
        forced_dot_damage_per_bullet = sum(mult * forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.effective.status_damage * self.effective.faction_damage**2 * average_primed_chamber_multiplier
        # Total dot damage
        return (dot_damage_per_bullet + extra_slash_damage_per_bullet + forced_dot_damage_per_bullet) * (self.effective.multishot * self.beam_dot_multiplier() if include_multishot else 1)