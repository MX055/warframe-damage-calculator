from ..fields.attack_result import AttackResult
from ..utils.functions import clamp
from . import helpers
from .ranged_calculator import RangedCalculator


class PrimaryCalculator(RangedCalculator):
    def _compute_modded_stats(self, result: AttackResult) -> None:
        super()._compute_modded_stats(result)
        build, modded = result.build, result.modded
        modded.hunter_munitions = clamp(build.hunter_munitions, 0, 0.3)
        modded.primed_chamber = clamp(build.primed_chamber, 0, 1.4)
        modded.vigilante_bonus = clamp(build.vigilante_bonus, 0, 0.3)

    def _compute_effective_stats(self, result: AttackResult) -> None:
        super()._compute_effective_stats(result)
        modded, effective = result.modded, result.effective
        effective.hunter_munitions = modded.hunter_munitions
        effective.primed_chamber = modded.primed_chamber
        effective.vigilante_bonus = modded.vigilante_bonus
        effective.crit_chance += effective.vigilante_bonus
        effective.weakpoint_crit_chance += effective.vigilante_bonus

    def _compute_average_stats(self, result: AttackResult) -> None:
        super()._compute_average_stats(result)
        effective, average = result.effective, result.average
        average.primed_chamber_multiplier = 1 + effective.primed_chamber / effective.magazine_capacity
        average.flat_dph *= average.primed_chamber_multiplier
        average.flat_weakpoint_dph *= average.primed_chamber_multiplier
        helpers.refresh_dps_from_dph(average)

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False) -> float:
        return helpers.primary_flat_dotph(result, weakpoint=weakpoint, faction_damage=self._max_average_faction_damage(result))
