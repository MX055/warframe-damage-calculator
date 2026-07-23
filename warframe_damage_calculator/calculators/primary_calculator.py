from ..fields.attack_result import AttackResult
from ..utils.functions import clamp
from .ranged_calculator import RangedCalculator


class PrimaryCalculator(RangedCalculator):
    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, modded = result.build, result.modded
        modded.additive.hunter_munitions = clamp(build.additive.hunter_munitions, 0, 0.3)
        modded.additive.primed_chamber = clamp(build.additive.primed_chamber, 0, 1.4)
        modded.additive.vigilante_bonus = clamp(build.additive.vigilante_bonus, 0, 0.3)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        modded, effective = result.modded, result.effective
        effective.hunter_munitions = modded.additive.hunter_munitions
        effective.primed_chamber = modded.additive.primed_chamber
        effective.vigilante_bonus = modded.additive.vigilante_bonus
        effective.crit_chance += effective.vigilante_bonus
        effective.weakpoint_crit_chance += effective.vigilante_bonus

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        effective, average = result.effective, result.average
        average.primed_chamber_multiplier = 1 + effective.primed_chamber / effective.magazine_capacity
        average.flat_dph *= average.primed_chamber_multiplier
        average.flat_weakpoint_dph *= average.primed_chamber_multiplier
        self._refresh_dps_from_dph(average)

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False) -> float:
        damage, forced_procs = result.effective.damage, result.base.forced_procs
        effective, average = result.effective, result.average
        if damage.total_damage() <= 0:
            return 0.0
        faction_damage = self._max_average_faction_damage(result)
        crit_chance = average.weakpoint_crit_chance if weakpoint else average.crit_chance
        multiplier = self._hit_multiplier(crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        primed = 1 + effective.primed_chamber / effective.magazine_capacity
        hunter_procs = effective.hunter_munitions * min(crit_chance, 1)
        hunter_dpp = 2.1 * damage.total_damage() * max(effective.crit_damage, multiplier) * effective.status_damage * faction_damage ** 2 * primed
        hunter_damage = hunter_procs * hunter_dpp
        impact_ib = (damage.weight("impact") + forced_procs.get("impact")) * effective.internal_bleeding
        guaranteed_proc, fractional_proc = divmod(effective.status_chance, 1)
        ib_procs = impact_ib * effective.status_chance
        ib_dpp = 2.1 * damage.total_damage() * multiplier * effective.status_damage * faction_damage ** 2 * primed
        ib_damage = ib_procs * ib_dpp
        ib_probability = 1 - (1 - impact_ib) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_ib))
        overlap = hunter_procs * ib_probability * min(hunter_dpp, ib_dpp)
        extra = hunter_damage + ib_damage - overlap
        return super()._flat_dotph(result, weakpoint=weakpoint, damage_multiplier=primed, extra_damage=extra * effective.multishot, faction_damage=faction_damage)
