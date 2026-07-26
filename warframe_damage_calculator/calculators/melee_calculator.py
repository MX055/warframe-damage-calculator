from ..fields.attack_result import AttackResult
from ..fields.upgrade import StanceCombo
from ..utils.constants import COMBO_HIT_INTERVAL, HEAVY_ATTACK_CATEGORIES, MAX_COMBO_MULTIPLIER, SLAM_ATTACK_CATEGORIES, SLIDE_ATTACK_CATEGORIES
from ..utils.functions import clamp, true_round
from ..utils.types import Number
from . import application_chance, formulas
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator):
    @staticmethod
    def _combo_multiplier_from_hits(hits: Number) -> int:
        return max(1, min(MAX_COMBO_MULTIPLIER, int(hits) // COMBO_HIT_INTERVAL + 1))

    def _crit_upgrade_multiplier(self, result: AttackResult) -> float:
        return 2.0 if result.category in HEAVY_ATTACK_CATEGORIES else 1.0

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
        modded.proportional.heavy_attack_speed = max(1 + build.proportional.heavy_attack_speed + evo.proportional.heavy_attack_speed, 0)
        speed = modded.proportional.heavy_attack_speed if result.category in HEAVY_ATTACK_CATEGORIES else max(1 + build.proportional.attack_speed + evo.proportional.attack_speed, 0)
        modded.proportional.attack_speed = max(base.attack_speed * speed * self._stance_hits_per_second_factor(result), 0)
        modded.proportional.heavy_attack_efficiency = max(build.proportional.heavy_attack_efficiency + evo.proportional.heavy_attack_efficiency + float(stats.heavy_attack_efficiency or 0), 0)
        modded.proportional.initial_combo = max(build.proportional.initial_combo + evo.proportional.initial_combo + float(stats.initial_combo or 0), 0)
        modded.proportional.slam_damage = max(1 + build.proportional.slam_damage + evo.proportional.slam_damage, 0)
        modded.proportional.slide_crit_chance = max(1 + build.proportional.slide_crit_chance + evo.proportional.slide_crit_chance, 0)

    def _compute_effective(self, result: AttackResult) -> None:
        super()._compute_effective(result)
        effective, modded = result.effective, result.modded
        category = result.category
        effective.attack_speed = modded.proportional.attack_speed
        effective.melee_duplicate = clamp(application_chance.duplicate_chance(result.build.application_chance), 0, 1)
        effective.melee_doughty = clamp(application_chance.doughty_factor(result.build.conversions), 0, 1)
        effective.heavy_attack_speed = modded.proportional.heavy_attack_speed
        effective.heavy_attack_efficiency = modded.proportional.heavy_attack_efficiency
        effective.initial_combo = modded.proportional.initial_combo
        effective.slam_damage = modded.proportional.slam_damage
        effective.slide_crit_chance = modded.proportional.slide_crit_chance
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
        return max(1, min(MAX_COMBO_MULTIPLIER, int(self.weapon.data.runtime.combo)))

    def _status_hits(self, result: AttackResult) -> float:
        hits = super()._status_hits(result)
        build, stats, modded = result.build, result.attack.stats, result.modded
        crit_factor = formulas.fold_multiplicative_families(build, result.evolutions, modded, stat="crit_chance")
        chance = max(stats.crit_chance * (1 + build.proportional.crit_chance * self._crit_upgrade_multiplier(result)) * crit_factor + modded.flat.crit_chance, 0)
        duplicate = clamp(application_chance.duplicate_chance(result.build.application_chance), 0, 1)
        return hits + duplicate * max(0, 1 - abs(chance - 1))

    def _sustained_attack_rate(self, result: AttackResult) -> float:
        """Melee sustained hit rate from modded attack speed (includes stance hits/sec)."""
        if "attack_speed" not in result.modded.proportional: return super()._sustained_attack_rate(result)
        return max(float(result.modded.proportional.attack_speed), 0)

    def _compute_average(self, result: AttackResult) -> None:
        super()._compute_average(result)
        effective, average = result.effective, result.average
        hit_mult = formulas.hit_multiplier(average.crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
        combo = self._combo_multiplier(result)
        average.combo_multiplier = combo
        per = application_chance.doughty_per(result.build.conversions)
        average.melee_doughty_bonus = true_round(application_chance.doughty_crit_damage(puncture_weight=effective.damage.weight("puncture"), status_chance=effective.status_chance, factor=effective.melee_doughty, per=per), 1)
        average.melee_duplicate_multiplier = 1 + effective.melee_duplicate * max(0, 1 - abs(effective.crit_chance - 1))
        faction = self._max_average_faction_damage(result)
        shared = faction * hit_mult * average.melee_duplicate_multiplier * combo
        average.flat_dph = self._direct_damage(result) * shared
        average.flat_dps = effective.attack_speed * average.flat_dph
        average.flat_dotph = self._flat_dotph(result) * combo
        average.flat_dotps = effective.attack_speed * average.flat_dotph
        average.flat_weakpoint_dph = average.flat_weakpoint_dotph = average.flat_resistant_dph = average.flat_resistant_dotph = 0.0
        if self.weapon.target is not None:
            average.weakpoint_crit_chance = average.crit_chance
            average.weakpoint_crit_multiplier = average.crit_multiplier
            average.flat_weakpoint_dph = self._direct_damage(result, "weakpoint") * shared
            average.flat_resistant_dph = self._direct_damage(result, "resistant") * shared
            average.flat_weakpoint_dotph = self._flat_dotph(result, weakpoint=True) * combo
            average.flat_resistant_dotph = self._flat_dotph(result, resistant=True) * combo
        average.flat_weakpoint_dotps = effective.attack_speed * average.flat_weakpoint_dotph
        average.flat_resistant_dotps = effective.attack_speed * average.flat_resistant_dotph
        average.flat_weakpoint_dps = effective.attack_speed * average.flat_weakpoint_dph
        average.flat_resistant_dps = effective.attack_speed * average.flat_resistant_dph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
        average.total_resistant_dph = average.flat_resistant_dph + average.flat_resistant_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
        average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps
        average.total_resistant_dps = average.flat_resistant_dps + average.flat_resistant_dotps
