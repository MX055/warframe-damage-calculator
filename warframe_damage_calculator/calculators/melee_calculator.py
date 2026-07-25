from ..fields.attack_result import AttackResult
from ..fields.upgrade import StanceCombo
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
            initial_combo = float(self.weapon.build.results.total.additive.initial_combo or 0)
            runtime.combo = self._combo_multiplier_from_hits(initial_combo)
        return ("combo",)

    def _equipped_stance(self):
        for upgrade in self.weapon.build:
            if upgrade.data.compatibility.get("stance"): return upgrade
        return None

    def _stance_combo_key(self, result: AttackResult) -> str:
        category = result.category
        if category in HEAVY_ATTACK_CATEGORIES: return "heavy"
        if category in SLIDE_ATTACK_CATEGORIES: return "slide"
        if category == "slam": return "slam"
        return self.weapon.data.selected_stance_combo

    def _stance_combo(self, result: AttackResult) -> StanceCombo | None:
        stance = self._equipped_stance()
        if stance is None: return None
        combos = stance.data.combos
        key = self._stance_combo_key(result)
        combo = combos.get(key)
        if combo is None and key != "neutral": combo = combos.get("neutral")
        return combo if isinstance(combo, StanceCombo) else StanceCombo(combo) if combo is not None else None

    def _stance_hits_per_second_factor(self, result: AttackResult) -> float:
        """hits/duration at 1.0 attack speed; scales modded attack speed into hits/sec."""
        combo = self._stance_combo(result)
        if combo is None: return 1.0
        duration = float(combo.duration or 0)
        hits = float(combo.hits or 0)
        if duration <= 0 or hits <= 0: return 1.0
        return hits / duration

    def _stance_damage_multiplier(self, result: AttackResult) -> float:
        combo = self._stance_combo(result)
        if combo is None: return 1.0
        return max(float(combo.multiplier or 1.0), 0.0)

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        super()._compute_modded_scalars(result)
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded
        stats = result.attack.stats
        modded.additive.heavy_attack_speed = max(1 + build.additive.heavy_attack_speed + evo.additive.heavy_attack_speed, 0)
        speed = modded.additive.heavy_attack_speed if result.category in HEAVY_ATTACK_CATEGORIES else max(1 + build.additive.attack_speed + evo.additive.attack_speed, 0)
        modded.additive.attack_speed = max(base.attack_speed * speed * self._stance_hits_per_second_factor(result), 0)
        modded.additive.melee_duplicate = clamp(build.additive.melee_duplicate, 0, 1)
        modded.additive.melee_doughty = clamp(build.additive.melee_doughty, 0, 1)
        modded.additive.heavy_attack_efficiency = max(build.additive.heavy_attack_efficiency + evo.additive.heavy_attack_efficiency + float(stats.heavy_attack_efficiency or 0), 0)
        modded.additive.initial_combo = max(build.additive.initial_combo + evo.additive.initial_combo + float(stats.initial_combo or 0), 0)
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
        stance_multiplier = self._stance_damage_multiplier(result)
        effective.damage = effective.damage * stance_multiplier
        effective.damage_bonus = effective.damage_bonus * stance_multiplier
        if category in SLAM_ATTACK_CATEGORIES:
            effective.damage = effective.damage * effective.slam_damage
            effective.damage_bonus = effective.damage_bonus * effective.slam_damage
        if category in SLIDE_ATTACK_CATEGORIES:
            effective.crit_chance = effective.crit_chance * effective.slide_crit_chance

    def _combo_multiplier(self, result: AttackResult) -> int:
        if result.category not in HEAVY_ATTACK_CATEGORIES: return 1
        combo = self.weapon.data.runtime.get("combo")
        if combo is not None: return max(1, min(MAX_COMBO_MULTIPLIER, int(combo)))
        return self._combo_multiplier_from_hits(float(result.effective.initial_combo or 0))

    def _status_hits(self, result: AttackResult) -> float:
        hits = super()._status_hits(result)
        build, stats, modded = result.build, result.attack.stats, result.modded
        chance = max(stats.crit_chance * (1 + build.additive.crit_chance * self._crit_upgrade_multiplier(result)) * modded.multiplicative.crit_chance + modded.flat.crit_chance, 0)
        return hits + modded.additive.melee_duplicate * max(0, 1 - abs(chance - 1))

    def _sustained_attack_rate(self, result: AttackResult) -> float:
        """Melee sustained hit rate from modded attack speed (includes stance hits/sec)."""
        if "attack_speed" not in result.modded.additive: return super()._sustained_attack_rate(result)
        return max(float(result.modded.additive.attack_speed), 0)

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        effective, average = result.effective, result.average
        hit_mult = formulas.hit_multiplier(average.crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
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
