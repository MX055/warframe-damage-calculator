from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp
from .ranged_calculator import RangedCalculator
from .weapon_calculator import AttackBucket


class PrimaryCalculator(RangedCalculator):
    def _compute_modded_stats(self, bucket: AttackBucket) -> None:
        super()._compute_modded_stats(bucket)
        build, modded = bucket.build, bucket.modded

        modded.hunter_munitions = clamp(build.hunter_munitions, 0, 0.3)
        modded.primed_chamber = clamp(build.primed_chamber, 0, 1.4)
        modded.vigilante_bonus = clamp(build.vigilante_bonus, 0, 0.3)

    def _compute_effective_stats(self, bucket: AttackBucket) -> None:
        super()._compute_effective_stats(bucket)
        modded, effective = bucket.modded, bucket.effective
        effective.hunter_munitions = modded.hunter_munitions
        effective.primed_chamber = modded.primed_chamber
        effective.vigilante_bonus = modded.vigilante_bonus
        effective.crit_chance += effective.vigilante_bonus
        effective.weakpoint_crit_chance += effective.vigilante_bonus

    def _compute_average_stats(self, bucket: AttackBucket) -> None:
        super()._compute_average_stats(bucket)
        effective, average = bucket.effective, bucket.average
        average.primed_chamber_multiplier = 1 + effective.primed_chamber / effective.magazine_capacity
        average.flat_dph *= average.primed_chamber_multiplier
        average.flat_weakpoint_dph *= average.primed_chamber_multiplier
        average.flat_dps = average.fire_rate * average.flat_dph
        average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
        average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps

    def _flat_dotph(self, bucket: AttackBucket, *, weakpoint: bool = False) -> float:
        damage, forced_procs = bucket.effective.damage, bucket.base.forced_procs
        effective, average = bucket.effective, bucket.average
        if damage.total_damage() <= 0:
            return 0.0
        crit_chance = average.weakpoint_crit_chance if weakpoint else average.crit_chance
        crit_multiplier = average.weakpoint_crit_multiplier if weakpoint else average.crit_multiplier
        primed_chamber_multiplier = 1 + effective.primed_chamber / effective.magazine_capacity
        hunter_munitions_procs = effective.hunter_munitions * min(crit_chance, 1)
        hunter_munitions_dpp = 2.1 * damage.total_damage() * max(effective.crit_damage, crit_multiplier) * effective.status_damage * effective.faction_damage ** 2 * primed_chamber_multiplier
        hunter_munitions_damage = hunter_munitions_procs * hunter_munitions_dpp
        impact_internal_bleeding = (damage.weight("impact") + forced_procs.get("impact")) * effective.internal_bleeding
        guaranteed_proc, fractional_proc = divmod(effective.status_chance, 1)
        internal_bleeding_procs = impact_internal_bleeding * effective.status_chance
        internal_bleeding_dpp = 2.1 * damage.total_damage() * crit_multiplier * effective.status_damage * effective.faction_damage ** 2 * primed_chamber_multiplier
        internal_bleeding_damage = internal_bleeding_procs * internal_bleeding_dpp
        internal_bleeding_probability = 1 - (1 - impact_internal_bleeding) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_internal_bleeding))
        overlap_damage = hunter_munitions_procs * internal_bleeding_probability * min(hunter_munitions_dpp, internal_bleeding_dpp)
        extra_slash_damage = hunter_munitions_damage + internal_bleeding_damage - overlap_damage
        dot_damage = sum(multiplier * damage.get(damage_type) * damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * effective.status_chance * crit_multiplier * effective.status_damage * effective.faction_damage ** 2 * primed_chamber_multiplier
        forced_dot_damage = sum(multiplier * forced_procs.get(damage_type) * damage.get(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * crit_multiplier * effective.status_damage * effective.faction_damage ** 2 * primed_chamber_multiplier
        return (dot_damage + extra_slash_damage + forced_dot_damage) * effective.multishot * average.beam_dot_multiplier
