from ..fields.attack_result import AttackResult
from ..utils.functions import clamp
from . import helpers
from .ranged_calculator import RangedCalculator
from .weapon_calculator import WeaponCalculator


class SecondaryCalculator(RangedCalculator):
    def _compute_modded_stats(self, result: AttackResult) -> None:
        super()._compute_modded_stats(result)
        build, modded = result.build, result.modded
        modded.secondary_enervate = clamp(build.secondary_enervate, 0, 6)
        modded.secondary_encumber = clamp(build.secondary_encumber, 0, 0.24)

    def _compute_effective_stats(self, result: AttackResult) -> None:
        super()._compute_effective_stats(result)
        modded, effective = result.modded, result.effective
        effective.secondary_enervate = modded.secondary_enervate
        effective.secondary_encumber = modded.secondary_encumber

    def _compute_average_stats(self, result: AttackResult) -> None:
        WeaponCalculator._compute_average_stats(self, result)
        self._setup_ranged_averages(result)
        modded, effective, average = result.modded, result.effective, result.average
        secondary_enervate_bonus = self._average_secondary_enervate_bonus(modded.crit_chance * modded.multiplicative_crit_chance + modded.flat_crit_chance, result)
        weakpoint_secondary_enervate_bonus = self._average_secondary_enervate_bonus(modded.weakpoint_crit_chance * (modded.multiplicative_crit_chance + modded.multiplicative_weakpoint_crit_chance - 1) + modded.flat_crit_chance, result)

        average.secondary_enervate_bonus = secondary_enervate_bonus
        average.weakpoint_secondary_enervate_bonus = weakpoint_secondary_enervate_bonus
        average.crit_chance = effective.crit_chance + secondary_enervate_bonus
        average.weakpoint_crit_chance = effective.weakpoint_crit_chance + weakpoint_secondary_enervate_bonus
        average.crit_multiplier = helpers.crit_multiplier(average.crit_chance, effective.crit_damage)
        average.weakpoint_crit_multiplier = helpers.crit_multiplier(average.weakpoint_crit_chance, effective.crit_damage)
        self._apply_ranged_damage_averages(result)

    @staticmethod
    def _average_secondary_enervate_bonus(crit_chance: float, result: AttackResult, max_stacks: int = 500) -> float:
        rate = result.effective.secondary_enervate
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

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False) -> float:
        return helpers.secondary_flat_dotph(result, weakpoint=weakpoint)
