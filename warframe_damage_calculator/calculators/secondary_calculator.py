from ..fields.attack_result import AttackResult
from ..utils.functions import clamp
from .ranged_calculator import RangedCalculator
from .weapon_calculator import WeaponCalculator


class SecondaryCalculator(RangedCalculator):
    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, modded = result.build, result.modded
        modded.additive.secondary_enervate = clamp(build.additive.secondary_enervate, 0, 6)
        modded.additive.secondary_encumber = clamp(build.additive.secondary_encumber, 0, 0.24)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        modded, effective = result.modded, result.effective
        effective.secondary_enervate = modded.additive.secondary_enervate
        effective.secondary_encumber = modded.additive.secondary_encumber

    def _compute_average(self, result: AttackResult) -> None:
        WeaponCalculator._compute_average(self, result)
        self._setup_ranged_averages(result)
        modded, effective, average = result.modded, result.effective, result.average
        secondary_enervate_bonus = self._average_secondary_enervate_bonus(modded.additive.crit_chance * modded.multiplicative.crit_chance + modded.flat.crit_chance, result)
        weakpoint_secondary_enervate_bonus = self._average_secondary_enervate_bonus(modded.additive.weakpoint_crit_chance * (modded.multiplicative.crit_chance + modded.multiplicative.weakpoint_crit_chance - 1) + modded.flat.crit_chance, result)

        average.secondary_enervate_bonus = secondary_enervate_bonus
        average.weakpoint_secondary_enervate_bonus = weakpoint_secondary_enervate_bonus
        average.crit_chance = effective.crit_chance + secondary_enervate_bonus
        average.weakpoint_crit_chance = effective.weakpoint_crit_chance + weakpoint_secondary_enervate_bonus
        average.crit_multiplier = self._crit_multiplier(average.crit_chance, effective.crit_damage)
        average.weakpoint_crit_multiplier = self._crit_multiplier(average.weakpoint_crit_chance, effective.crit_damage)
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
        # Secondary Encumber calculations need testing in-game
        damage, forced_procs = result.effective.damage, result.base.forced_procs
        effective, average = result.effective, result.average
        if damage.total_damage() <= 0:
            return 0.0
        faction_damage = self._max_average_faction_damage(result)
        multiplier = self._hit_multiplier(average.weakpoint_crit_chance if weakpoint else average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        encumber_chance = 1 - (1 - effective.secondary_encumber * min(effective.status_chance, 1)) ** effective.multishot
        encumber_dot = encumber_chance * damage.total_damage() * 14.1 / 13 * multiplier * effective.status_damage * faction_damage ** 2
        ib_procs = ((damage.weight("impact") + forced_procs.get("impact")) * effective.status_chance + encumber_chance / 13) * effective.internal_bleeding
        ib_dpp = 2.1 * damage.total_damage() * multiplier * effective.status_damage * faction_damage ** 2
        extra = ib_procs * ib_dpp * effective.multishot
        return super()._flat_dotph(result, weakpoint=weakpoint, extra_damage=extra + encumber_dot, faction_damage=faction_damage)
