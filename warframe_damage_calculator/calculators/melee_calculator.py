from ..fields.attack_result import AttackResult
from ..utils.functions import clamp, true_round
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator):
    def _compute_modded_stats(self, result: AttackResult) -> None:
        super()._compute_modded_stats(result)
        build, base, modded = result.build, result.base, result.modded
        modded.attack_speed = max(base.attack_speed * (1 + build.attack_speed), 0)
        modded.melee_duplicate = clamp(build.melee_duplicate, 0, 1)
        modded.melee_doughty = clamp(build.melee_doughty, 0, 1)

    def _compute_effective_stats(self, result: AttackResult) -> None:
        super()._compute_effective_stats(result)
        effective, modded = result.effective, result.modded
        effective.attack_speed = modded.attack_speed
        effective.melee_duplicate = modded.melee_duplicate
        effective.melee_doughty = modded.melee_doughty

    def _compute_average_stats(self, result: AttackResult) -> None:
        super()._compute_average_stats(result)
        effective, average = result.effective, result.average
        average.melee_doughty_bonus = true_round(10 * effective.damage.weight("puncture") * effective.status_chance * effective.melee_doughty, 1)
        average.melee_duplicate_multiplier = 1 + effective.melee_duplicate * max(0, 1 - abs(effective.crit_chance - 1))
        average.flat_dph = effective.damage.total_damage() * self._max_average_faction_damage(result) * average.crit_multiplier * average.melee_duplicate_multiplier
        average.flat_dps = effective.attack_speed * average.flat_dph
        average.flat_dotph = self._flat_dotph(result)
        average.flat_dotps = effective.attack_speed * average.flat_dotph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
