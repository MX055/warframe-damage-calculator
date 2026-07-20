from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp
from .ranged_calculator import RangedCalculator
from .weapon_calculator import AttackBucket


class SecondaryCalculator(RangedCalculator):
    def _compute_modded_stats(self, bucket: AttackBucket) -> None:
        super()._compute_modded_stats(bucket)
        build, modded = bucket.build, bucket.modded

        modded.secondary_enervate = clamp(build.secondary_enervate, 0, 6)
        modded.secondary_encumber = clamp(build.secondary_encumber, 0, 0.24)

    def _compute_effective_stats(self, bucket: AttackBucket) -> None:
        super()._compute_effective_stats(bucket)
        modded, effective = bucket.modded, bucket.effective

        effective.secondary_enervate = modded.secondary_enervate
        effective.secondary_encumber = modded.secondary_encumber

    def _compute_average_stats(self, bucket: AttackBucket) -> None:
        super()._compute_average_stats(bucket)
        modded, effective, average = bucket.modded, bucket.effective, bucket.average
        secondary_enervate_bonus = self._average_secondary_enervate_bonus(modded.crit_chance * modded.multiplicative_crit_chance + modded.flat_crit_chance, bucket)
        weakpoint_secondary_enervate_bonus = self._average_secondary_enervate_bonus(modded.weakpoint_crit_chance * (modded.multiplicative_crit_chance + modded.multiplicative_weakpoint_crit_chance - 1) + modded.flat_crit_chance, bucket)

        average.secondary_enervate_bonus = secondary_enervate_bonus
        average.weakpoint_secondary_enervate_bonus = weakpoint_secondary_enervate_bonus
        average.crit_chance = effective.crit_chance + secondary_enervate_bonus
        average.weakpoint_crit_chance = effective.weakpoint_crit_chance + weakpoint_secondary_enervate_bonus
        average.crit_multiplier = 1 + average.crit_chance * (effective.crit_damage - 1)
        average.weakpoint_crit_multiplier = 1 + average.weakpoint_crit_chance * (effective.crit_damage - 1)
        average.flat_dph = effective.damage.total_damage() * effective.multishot * effective.faction_damage * average.crit_multiplier
        average.flat_weakpoint_dph = effective.damage.total_damage() * effective.multishot * effective.weakpoint_damage * average.weakpoint_crit_multiplier * effective.faction_damage
        average.flat_dps = average.fire_rate * average.flat_dph
        average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
        average.flat_dotph = self._flat_dotph(bucket)
        average.flat_weakpoint_dotph = self._flat_dotph(bucket, weakpoint=True)
        average.flat_dotps = average.fire_rate * average.flat_dotph
        average.flat_weakpoint_dotps = average.fire_rate * average.flat_weakpoint_dotph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
        average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps

    @staticmethod
    def _average_secondary_enervate_bonus(crit_chance: float, bucket: AttackBucket, max_stacks: int = 500) -> float:
        rate = bucket.effective.secondary_enervate
        if rate == 0:
            return 0.0
        length = [[0.0] * rate for _ in range(max_stacks + 1)]
        accumulated = [[0.0] * rate for _ in range(max_stacks + 1)]

        probability = max(0.0, min(1.0, crit_chance + 0.1 * max_stacks - 1))
        miss = 1.0 - probability
        if miss == 1.0:
            return float("inf")

        length[max_stacks][rate - 1] = 1.0 / (1.0 - miss)
        accumulated[max_stacks][rate - 1] = max_stacks / (1.0 - miss)
        for index in range(rate - 2, -1, -1):
            length[max_stacks][index] = (1.0 + probability * length[max_stacks][index + 1]) / (1.0 - miss)
            accumulated[max_stacks][index] = (max_stacks + probability * accumulated[max_stacks][index + 1]) / (1.0 - miss)

        for stack in range(max_stacks - 1, -1, -1):
            probability = max(0.0, min(1.0, crit_chance + 0.1 * stack - 1))
            miss = 1.0 - probability
            length[stack][rate - 1] = 1.0 + miss * length[stack + 1][rate - 1]
            accumulated[stack][rate - 1] = stack + miss * accumulated[stack + 1][rate - 1]
            for index in range(rate - 2, -1, -1):
                length[stack][index] = 1.0 + miss * length[stack + 1][index] + probability * length[stack + 1][index + 1]
                accumulated[stack][index] = stack + miss * accumulated[stack + 1][index] + probability * accumulated[stack + 1][index + 1]

        return 0.1 * accumulated[0][0] / length[0][0]

    def _flat_dotph(self, bucket: AttackBucket, *, weakpoint: bool = False) -> float:  # Secondary Encumber calculations need testing in-game
        damage, forced_procs = bucket.effective.damage, bucket.base.forced_procs
        effective, average = bucket.effective, bucket.average
        if damage.total_damage() <= 0:
            return 0.0
        crit_multiplier = average.weakpoint_crit_multiplier if weakpoint else average.crit_multiplier
        secondary_encumber_chance = 1 - (1 - effective.secondary_encumber * min(effective.status_chance, 1)) ** effective.multishot
        secondary_encumber_dot = secondary_encumber_chance * damage.total_damage() * 14.1 / 13 * crit_multiplier * effective.status_damage * effective.faction_damage ** 2
        internal_bleeding_procs = ((damage.weight("impact") + forced_procs.get("impact")) * effective.status_chance + secondary_encumber_chance / 13) * effective.internal_bleeding
        internal_bleeding_dpp = 2.1 * damage.total_damage() * crit_multiplier * effective.status_damage * effective.faction_damage ** 2
        internal_bleeding_damage = internal_bleeding_procs * internal_bleeding_dpp
        dot_damage = sum(multiplier * damage.get(damage_type) * damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * effective.status_chance * crit_multiplier * effective.status_damage * effective.faction_damage ** 2
        forced_dot_damage = sum(multiplier * forced_procs.get(damage_type) * damage.get(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * crit_multiplier * effective.status_damage * effective.faction_damage ** 2
        return (dot_damage + internal_bleeding_damage + forced_dot_damage) * effective.multishot * average.beam_dot_multiplier + secondary_encumber_dot
