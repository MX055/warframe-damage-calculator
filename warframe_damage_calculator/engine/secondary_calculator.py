from ..fields.attack_result import AttackResult
from ..utils.constants import DOT_MULTIPLIERS
from ..utils.types import Number
from . import application_chance, formulas, stacking_reset, target
from .ranged_calculator import RangedCalculator


class SecondaryCalculator(RangedCalculator):
    def _average_crit_chances(self, result: AttackResult) -> tuple[float, float]:
        effective, average = result.effective, result.average
        per_stack, charges = stacking_reset.enervate_params(result.build.stacking_reset)
        secondary_enervate_bonus = stacking_reset.average_enervate_bonus(effective.crit_chance, per_stack=per_stack, reset_charges=charges)
        weakpoint_secondary_enervate_bonus = stacking_reset.average_enervate_bonus(effective.weakpoint_crit_chance, per_stack=per_stack, reset_charges=charges)
        average.secondary_enervate_bonus = secondary_enervate_bonus
        average.weakpoint_secondary_enervate_bonus = weakpoint_secondary_enervate_bonus
        return float(effective.crit_chance + secondary_enervate_bonus), float(effective.weakpoint_crit_chance + weakpoint_secondary_enervate_bonus)

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False, resistant: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number | None = None) -> float:
        damage = result.effective.damage
        effective, average = result.effective, result.average
        if damage.total_damage() <= 0: return 0.0
        if faction_damage is None: faction_damage = self._max_average_faction_damage(result)
        continuous = (result.attack.delivery or "") == "beam"
        multiplier = formulas.hit_multiplier(average.weakpoint_crit_chance if weakpoint else average.crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        encumber = application_chance.encumber_chance(result.build.application_chance)
        encumber_chance = 1 - (1 - encumber * min(effective.status_chance, 1)) ** effective.multishot
        tick_damage = damage.total_damage() * (effective.multishot if continuous else 1.0)
        zone = "weakpoint" if weakpoint else "resistant" if resistant else "normal"
        encumber_dot_factor = sum(factor * target.damage_type_multiplier(self.weapon.target, damage_type, dot=True, status_effects=result.status_effects, zone=zone, weakpoint_bonus=self._weakpoint_damage_bonus(result)) for damage_type, factor in DOT_MULTIPLIERS) * effective.status_duration
        encumber_dot = encumber_chance * tick_damage * encumber_dot_factor / 13 * multiplier * effective.status_damage * faction_damage ** 2
        ib_procs = (self._impact_weight(result) * effective.status_chance + encumber_chance / 13) * self._internal_bleeding_chance(result)
        tick_damage_scale = effective.multishot if continuous else 1.0
        ib_dpp = self._ib_slash_dot_per_proc(result, hit_multiplier=multiplier, faction_damage=faction_damage, damage_multiplier=tick_damage_scale, weakpoint=weakpoint, resistant=resistant)
        extra_hits = 1.0 if continuous else effective.multishot
        extra = ib_procs * ib_dpp * extra_hits
        return super()._flat_dotph(result, weakpoint=weakpoint, resistant=resistant, hits=hits, damage_multiplier=damage_multiplier, extra_damage=extra + encumber_dot + extra_damage, faction_damage=faction_damage)
