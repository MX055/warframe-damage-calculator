from ..fields.attack_result import AttackResult
from ..utils.types import Number
from . import application_chance, formulas
from .ranged_calculator import RangedCalculator


class PrimaryCalculator(RangedCalculator):
    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        vigilante = application_chance.vigilante_flat_crit(result.build.application_chance)
        result.effective.crit_chance += vigilante
        result.effective.weakpoint_crit_chance += vigilante

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False, resistant: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number | None = None) -> float:
        damage = result.effective.damage
        effective, average = result.effective, result.average
        if damage.total_damage() <= 0: return 0.0
        if faction_damage is None: faction_damage = self._max_average_faction_damage(result)
        continuous = (result.attack.delivery or "") == "beam"
        crit_chance = average.weakpoint_crit_chance if weakpoint else average.crit_chance
        multiplier = formulas.hit_multiplier(crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        tick_damage_scale = effective.multishot if continuous else 1.0
        hunter = application_chance.hunter_munitions_chance(result.build.application_chance)
        hunter_procs = hunter * min(crit_chance, 1)
        hunter_dpp = self._ib_slash_dot_per_proc(result, hit_multiplier=max(effective.crit_damage, multiplier), faction_damage=faction_damage, damage_multiplier=damage_multiplier * tick_damage_scale, weakpoint=weakpoint, resistant=resistant)
        hunter_damage = hunter_procs * hunter_dpp
        impact_ib = self._impact_weight(result) * self._internal_bleeding_chance(result)
        guaranteed_proc, fractional_proc = divmod(effective.status_chance, 1)
        ib_procs = impact_ib * effective.status_chance
        ib_dpp = self._ib_slash_dot_per_proc(result, hit_multiplier=multiplier, faction_damage=faction_damage, damage_multiplier=damage_multiplier * tick_damage_scale, weakpoint=weakpoint, resistant=resistant)
        ib_damage = ib_procs * ib_dpp
        ib_probability = 1 - (1 - impact_ib) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_ib))
        overlap = hunter_procs * ib_probability * min(hunter_dpp, ib_dpp)
        extra = hunter_damage + ib_damage - overlap
        extra_hits = 1.0 if continuous else effective.multishot
        return super()._flat_dotph(result, weakpoint=weakpoint, resistant=resistant, hits=hits, damage_multiplier=damage_multiplier, extra_damage=extra * extra_hits + extra_damage, faction_damage=faction_damage)
