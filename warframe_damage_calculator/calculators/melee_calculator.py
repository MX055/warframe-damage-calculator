from ..fields.attack_result import AttackResult
from ..utils.functions import clamp, true_round
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator):
    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded
        modded.additive.attack_speed = max(base.attack_speed * (1 + build.additive.attack_speed + evo.additive.attack_speed), 0)
        modded.additive.melee_duplicate = clamp(build.additive.melee_duplicate, 0, 1)
        modded.additive.melee_doughty = clamp(build.additive.melee_doughty, 0, 1)
        modded.additive.range = max(float(base.get("range", 0) or 0) + build.additive.range + build.flat.range + evo.additive.range + evo.flat.range, 0)
        modded.additive.heavy_attack_speed = max(1 + build.additive.heavy_attack_speed + evo.additive.heavy_attack_speed, 0)
        modded.additive.initial_combo = max(build.additive.initial_combo + evo.additive.initial_combo, 0)
        modded.additive.slam_damage = max(1 + build.additive.slam_damage + evo.additive.slam_damage, 0)
        modded.additive.slide_crit_chance = max(1 + build.additive.slide_crit_chance + evo.additive.slide_crit_chance, 0)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        effective, modded = result.effective, result.modded
        effective.attack_speed = modded.additive.attack_speed
        effective.melee_duplicate = modded.additive.melee_duplicate
        effective.melee_doughty = modded.additive.melee_doughty
        effective.range = modded.additive.range
        effective.heavy_attack_speed = modded.additive.heavy_attack_speed
        effective.initial_combo = modded.additive.initial_combo
        effective.slam_damage = modded.additive.slam_damage
        effective.slide_crit_chance = modded.additive.slide_crit_chance

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        effective, average = result.effective, result.average
        hit_mult = self._hit_multiplier(average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        average.melee_doughty_bonus = true_round(10 * effective.damage.weight("puncture") * effective.status_chance * effective.melee_doughty, 1)
        average.melee_duplicate_multiplier = 1 + effective.melee_duplicate * max(0, 1 - abs(effective.crit_chance - 1))
        average.flat_dph = effective.damage.total_damage() * self._max_average_faction_damage(result) * hit_mult * average.melee_duplicate_multiplier
        average.flat_dps = effective.attack_speed * average.flat_dph
        average.flat_dotph = self._flat_dotph(result)
        average.flat_dotps = effective.attack_speed * average.flat_dotph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
