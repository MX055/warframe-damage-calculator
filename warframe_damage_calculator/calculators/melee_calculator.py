from ..fields.attack_result import AttackResult
from ..utils.constants import COMBO_HIT_INTERVAL, HEAVY_ATTACK_CATEGORIES, MAX_COMBO_MULTIPLIER, SLAM_ATTACK_CATEGORIES, SLIDE_ATTACK_CATEGORIES
from ..utils.functions import clamp, true_round
from ..utils.types import Number
from . import formulas
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator):
    @staticmethod
    def _combo_multiplier_from_hits(hits: Number) -> int:
        return max(1, min(MAX_COMBO_MULTIPLIER, int(hits) // COMBO_HIT_INTERVAL + 1))

    def _crit_upgrade_multiplier(self, result: AttackResult) -> float:
        return 2.0 if result.category in HEAVY_ATTACK_CATEGORIES else 1.0

    def _runtime_defaults(self) -> tuple[str, ...]:
        runtime = self.weapon.data.runtime
        if "combo" in runtime: return ()
        runtime.combo = MAX_COMBO_MULTIPLIER
        if self._selected_category() in HEAVY_ATTACK_CATEGORIES:
            self.weapon.build.results.resolve(self.weapon.data)
            initial_combo = float(self.weapon.build.results.total.additive.get("initial_combo", 0) or 0)
            runtime.combo = self._combo_multiplier_from_hits(initial_combo)
        return ("combo",)

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded
        stats = result.attack.stats
        modded.additive.attack_speed = max(base.attack_speed * (1 + build.additive.attack_speed + evo.additive.attack_speed), 0)
        modded.additive.melee_duplicate = clamp(build.additive.melee_duplicate, 0, 1)
        modded.additive.melee_doughty = clamp(build.additive.melee_doughty, 0, 1)
        modded.additive.heavy_attack_speed = max(1 + build.additive.heavy_attack_speed + evo.additive.heavy_attack_speed, 0)
        modded.additive.heavy_attack_efficiency = max(float(build.additive.get("heavy_attack_efficiency", 0) or 0) + float(evo.additive.get("heavy_attack_efficiency", 0) or 0) + float(stats.get("heavy_attack_efficiency", 0) or 0), 0)
        modded.additive.initial_combo = max(build.additive.initial_combo + evo.additive.initial_combo + float(stats.get("initial_combo", 0) or 0), 0)
        modded.additive.slam_damage = max(1 + build.additive.slam_damage + evo.additive.slam_damage, 0)
        modded.additive.slide_crit_chance = max(1 + build.additive.slide_crit_chance + evo.additive.slide_crit_chance, 0)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        effective, modded = result.effective, result.modded
        category = result.category
        effective.attack_speed = modded.additive.attack_speed
        effective.melee_duplicate = modded.additive.melee_duplicate
        effective.melee_doughty = modded.additive.melee_doughty
        effective.heavy_attack_speed = modded.additive.heavy_attack_speed
        effective.heavy_attack_efficiency = modded.additive.heavy_attack_efficiency
        effective.initial_combo = modded.additive.initial_combo
        effective.slam_damage = modded.additive.slam_damage
        effective.slide_crit_chance = modded.additive.slide_crit_chance
        if category in SLAM_ATTACK_CATEGORIES and effective.slam_damage != 1:
            effective.damage = effective.damage * effective.slam_damage
            effective.damage_bonus = effective.damage_bonus * effective.slam_damage
        if category in SLIDE_ATTACK_CATEGORIES and effective.slide_crit_chance != 1:
            effective.crit_chance = effective.crit_chance * effective.slide_crit_chance

    def _combo_multiplier(self, result: AttackResult) -> int:
        if result.category not in HEAVY_ATTACK_CATEGORIES: return 1
        combo = self.weapon.data.runtime.get("combo")
        if combo is not None: return max(1, min(MAX_COMBO_MULTIPLIER, int(combo)))
        return self._combo_multiplier_from_hits(float(result.effective.get("initial_combo", 0) or 0))

    def _status_hits(self, result: AttackResult) -> float:
        hits = super()._status_hits(result)
        build, stats, modded = result.build, result.attack.stats, result.modded
        duplicate = modded.additive.get("melee_duplicate", 0)
        crit_mods = self._crit_upgrade_multiplier(result)
        chance = max(stats.crit_chance * (1 + build.additive.crit_chance * crit_mods) * modded.multiplicative.crit_chance + modded.flat.crit_chance, 0)
        return hits + duplicate * max(0, 1 - abs(chance - 1))

    def _sustained_attack_rate(self, result: AttackResult) -> float:
        """Melee sustained attack rate from modded attack speed."""
        stats, base, modded = result.attack.stats, result.base, result.modded
        if "attack_speed" not in modded.additive: return super()._sustained_attack_rate(result)
        return max(stats.fire_rate * modded.additive.attack_speed / (base.attack_speed or 1), 0)

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        effective, average = result.effective, result.average
        hit_mult = formulas.hit_multiplier(average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        combo = self._combo_multiplier(result)
        average.combo_multiplier = combo
        average.melee_doughty_bonus = true_round(10 * effective.damage.weight("puncture") * effective.status_chance * effective.melee_doughty, 1)
        average.melee_duplicate_multiplier = 1 + effective.melee_duplicate * max(0, 1 - abs(effective.crit_chance - 1))
        average.flat_dph = effective.damage.total_damage() * self._max_average_faction_damage(result) * hit_mult * average.melee_duplicate_multiplier * combo
        average.flat_dps = effective.attack_speed * average.flat_dph
        average.flat_dotph = self._flat_dotph(result) * combo
        average.flat_dotps = effective.attack_speed * average.flat_dotph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
