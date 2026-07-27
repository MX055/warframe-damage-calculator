"""Weapon calculation orchestration.

Coordinates the per-attack pipeline and category-specific hooks. Shared formulas,
scalar folds, damage Dist construction, and sustained status live in sibling modules.
"""

from __future__ import annotations

from ..fields.attack_result import AttackResult
from ..fields.calculated import ModdedStats
from ..fields.evolution import ResolvedEvolutionStat
from ..fields.upgrade import ResolvedStat
from ..fields.weapon_data import Attack
from ..protocols import BuildUpgradeOwner, ConfigurableWeaponOwner
from ..utils.types import ContributionTarget, Number
from . import attack_tree, damage_calculator, formulas, scalar_calculator, target_calculator
from .contributions import ContributionCalculator
from .evolution_calculator import EvolutionCalculator
from .status_model import SustainedStatusModel, apply_condition_overload, build_sustained_status_model, condition_overload_bonus, non_dot_status_effects, status_effect_stack_bonuses

CONTRIBUTION_TARGETS = frozenset({"flat_dph", "flat_weakpoint_dph", "flat_resistant_dph", "flat_dps", "flat_weakpoint_dps", "flat_resistant_dps", "flat_dotph", "flat_weakpoint_dotph", "flat_resistant_dotph", "flat_dotps", "flat_weakpoint_dotps", "flat_resistant_dotps", "total_dph", "total_weakpoint_dph", "total_resistant_dph", "total_dps", "total_weakpoint_dps", "total_resistant_dps"})


class WeaponCalculator:
    def __init__(self, weapon: ConfigurableWeaponOwner) -> None:
        self.weapon = weapon
        self._main = AttackResult()
        self._child: list[AttackResult] = []
        self._inputs_fingerprint: object | None = None
        self._contribution_upgrades: list[BuildUpgradeOwner] | None = None
        self.resolve()

    # --- resolve wiring ---

    def _resolved_build(self) -> ResolvedStat:
        build = self.weapon.build
        build.results.resolve(self.weapon.data)
        return build.results.total

    def _selected_category(self) -> str:
        return self.weapon.data.attacks[self.weapon.data.selected_attack].category

    def _crit_upgrade_multiplier(self, result: AttackResult) -> float:
        return 1.0

    def _resolved_evolutions(self, attack: Attack | None = None) -> ResolvedEvolutionStat:
        if not self.weapon.data.evolutions: return ResolvedEvolutionStat()
        if attack is None: attack = self.weapon.data.attacks[self.weapon.data.selected_attack]
        form = attack.form
        return EvolutionCalculator(self.weapon, self.weapon.data.runtime, form=form).total

    def _fingerprint_runtime(self) -> tuple:
        """Capture runtime/build inputs so direct runtime mutations recompute results."""
        runtime = self.weapon.data.runtime
        return (id(self.weapon.build), tuple(sorted((str(key), repr(runtime[key])) for key in runtime)), target_calculator.fingerprint(self.weapon.target))

    def _ensure_resolved(self) -> None:
        fingerprint = self._fingerprint_runtime()
        if fingerprint != self._inputs_fingerprint: self.resolve()

    # --- per-attack pipeline ---

    def _compute_attack(self, name: str, attack: Attack, resolved_build: ResolvedStat, resolved_evolutions: ResolvedEvolutionStat) -> AttackResult:
        result = AttackResult({"name": name, "attack": attack, "build": resolved_build, "evolutions": resolved_evolutions, "children": list(attack.children)})
        self._compute_base(result)
        self._apply_evolution_conversions(result)
        self._compute_modded_scalars(result)
        model = self._sustained_status_model(result)
        self._apply_status_effect_stacks(result, model)
        self._apply_condition_overload(result, model)
        self._compute_modded_damage(result)
        self._compute_effective(result)
        result.status_effects = non_dot_status_effects(model)
        self._compute_average(result)
        target_calculator.mask_missing_bodypart_metrics(result.average, self.weapon.target)
        return result

    def _ability_strength_multiplier(self) -> float | None:
        """Return Ability Strength multiplier for exalted/pseudo-exalted weapons.

        Arsenal damage is stored at 100% Strength. Runtime `ability_strength` is a
        multiplier (1.0 = 100%, 2.5 = 250%). Non-exalted weapons ignore the key.
        """
        data = self.weapon.data
        if not (data.get("exalted") or data.get("pseudo_exalted")):
            return None
        return max(float(data.runtime.ability_strength), 0.0)

    def _compute_base(self, result: AttackResult) -> None:
        result.base, result.original_damage = scalar_calculator.seed_base_stats(attack=result.attack, ammo=self.weapon.data.ammo, stats_type=self.weapon.stats_type, evolutions=result.evolutions, distribute_flat=formulas.distribute_flat_damage, ability_strength=self._ability_strength_multiplier())

    def _apply_evolution_conversions(self, result: AttackResult) -> None:
        scalar_calculator.apply_evolution_conversions(base=result.base, build=result.build, evolutions=result.evolutions, crit_upgrade_multiplier=self._crit_upgrade_multiplier(result))

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        scalar_calculator.compute_shared_modded_scalars(base=result.base, build=result.build, evolutions=result.evolutions, modded=result.modded, attack=result.attack, crit_upgrade_multiplier=self._crit_upgrade_multiplier(result))

    def _status_hits(self, result: AttackResult) -> float:
        """Status attempts per attack (typically multishot; melee may add duplicate hits)."""
        stats, modded = result.attack.stats, result.modded
        return max(modded.proportional.multishot, 1)

    def _sustained_attack_rate(self, result: AttackResult) -> float:
        """Sustained attacks/sec for status production and average fire rate.

        Base returns the attack's raw fire_rate as a pre-modded fallback. Category
        calculators override with magazine-cycle or attack-speed sustained rates.
        """
        stats = result.attack.stats
        return max(float(stats.attack_speed if "attack_speed" in stats else stats.fire_rate or 0), 0)

    def _effective_attacks_per_second(self, result: AttackResult) -> float:
        """Compatibility alias for sustained attack rate (tests and tree fold)."""
        return self._sustained_attack_rate(result)

    def _sustained_status_model(self, result: AttackResult) -> SustainedStatusModel:
        return build_sustained_status_model(attack=result.attack, base=result.base, modded=result.modded, build=result.build, evolution_status_chance=result.evolutions.proportional.status_chance, status_attempts_per_attack=self._status_hits(result), sustained_attack_rate=self._sustained_attack_rate(result), evolution_damage_types=result.evolutions.proportional.damage_types)

    def _average_condition_overload_bonus(self, result: AttackResult) -> float:
        model = self._sustained_status_model(result)
        if model.max_unique_statuses <= 0: return 0.0
        return condition_overload_bonus(model, value_per_status=result.build.proportional.condition_overload.value, co_factor=result.attack.stats.co_factor, co_effect=result.attack.stats.co_effect).bonus

    def _apply_status_effect_stacks(self, result: AttackResult, model: SustainedStatusModel | None = None) -> None:
        """Apply automatic status_effect_stacks bonuses from sustained proc expectations.

        Injects expected stacks into a per-attack build copy and recomputes modded scalars
        so category-specific folds stay consistent. Does not rebuild the status model, so
        multishot/status bonuses do not feed back. Runtime cannot override automatic effects.
        """
        entries = list(result.build.proportional.status_effect_stacks)
        if not entries: return
        model = model or self._sustained_status_model(result)
        bonuses = status_effect_stack_bonuses(model=model, entries=entries)
        if not bonuses: return
        result.build = result.build.copy()
        for mode, stat, bonus in bonuses:
            bucket = getattr(result.build, mode)
            bucket[stat] = float(bucket[stat] if stat in bucket else 0) + bonus
        result.modded = ModdedStats()
        self._compute_modded_scalars(result)

    def _apply_condition_overload(self, result: AttackResult, model: SustainedStatusModel | None = None) -> None:
        model = model or self._sustained_status_model(result)
        if model.max_unique_statuses <= 0: return
        if not float(result.build.proportional.condition_overload.value or 0): return
        apply_condition_overload(modded=result.modded, model=model, value_per_status=result.build.proportional.condition_overload.value, co_factor=result.attack.stats.co_factor, co_effect=result.attack.stats.co_effect)

    def _compute_modded_damage(self, result: AttackResult) -> None:
        damage_calculator.compute_modded_damage(attack=result.attack, base=result.base, original_damage=result.original_damage, build=result.build, evolutions=result.evolutions, modded=result.modded)

    def _compute_effective(self, result: AttackResult) -> None:
        scalar_calculator.compute_shared_effective(base=result.base, modded=result.modded, effective=result.effective, build=result.build, evolutions=result.evolutions)

    def _max_average_faction_damage(self, result: AttackResult) -> float:
        return target_calculator.faction_damage(result.average, self.weapon.target)

    def _weakpoint_damage_bonus(self, result: AttackResult) -> float:
        return 0.0

    def _direct_damage(self, result: AttackResult, zone: target_calculator.HitZone = "normal") -> float:
        if self.weapon.target is None: return float(result.effective.damage.total_damage()) if zone == "normal" else 0.0
        return target_calculator.damage_total(result.effective.damage, self.weapon.target, status_effects=result.status_effects, zone=zone, weakpoint_bonus=self._weakpoint_damage_bonus(result))

    def _compute_average(self, result: AttackResult) -> None:
        damage_calculator.apply_shared_average_factions(effective=result.effective, average=result.average)
        damage_calculator.apply_shared_average_crit(effective=result.effective, average=result.average)

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False, resistant: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number | None = None) -> float:
        # Allow unbound helper-test calls with self=None (status attempts unused when damage is empty).
        if resistant and self is not None and self.weapon.target is None: return 0.0
        if self is None: status_attempts = max(result.modded.proportional.multishot if "multishot" in result.modded.proportional else result.attack.stats.multishot, 1)
        else: status_attempts = self._status_hits(result)
        return damage_calculator.flat_dotph_from_result(result, status_attempts_per_attack=status_attempts, weakpoint=weakpoint, resistant=resistant, hits=hits, damage_multiplier=damage_multiplier, extra_damage=extra_damage, faction_damage=faction_damage, target=None if self is None else self.weapon.target, status_effects=None if self is None else result.status_effects, weakpoint_bonus=0 if self is None else self._weakpoint_damage_bonus(result))

    # --- tree + resolve ---

    def _compute_attack_results(self, resolved_build: ResolvedStat, resolved_evolutions: ResolvedEvolutionStat | None = None) -> dict[str, AttackResult]:
        return attack_tree.compute_attack_results(
            attacks=self.weapon.data.attacks,
            selected=self.weapon.data.selected_attack,
            compute_attack=lambda name, attack: self._compute_attack(name, attack, resolved_build, resolved_evolutions if resolved_evolutions is not None else self._resolved_evolutions(attack)),
            attack_rate_for=self._sustained_attack_rate,
        )

    def _metric_for_build(self, resolved_build: ResolvedStat, resolved_evolutions: ResolvedEvolutionStat, target: ContributionTarget, upgrades: list[BuildUpgradeOwner] | None = None) -> float:
        self._contribution_upgrades = upgrades
        try:
            results = self._compute_attack_results(resolved_build, resolved_evolutions)
            return float(results[self.weapon.data.selected_attack].final.get(target, 0) or 0)
        finally:
            self._contribution_upgrades = None

    def resolve(self, *, validate_cycles: bool = True) -> None:
        fingerprint = self._fingerprint_runtime()
        if validate_cycles: attack_tree.validate_attack_cycles(self.weapon.data.attacks)
        results = self._compute_attack_results(self._resolved_build())
        self._main = results[self.weapon.data.selected_attack]
        self._child = [results[name] for name in self._main.children if name in results]
        self._inputs_fingerprint = fingerprint

    @property
    def main(self) -> AttackResult:
        self._ensure_resolved()
        return self._main

    @property
    def child(self) -> list[AttackResult]:
        self._ensure_resolved()
        return self._child

    # --- contributions ---

    @staticmethod
    def _upgrade_depends_on_equipped(upgrade: BuildUpgradeOwner) -> bool:
        return any(getattr(effect, "equipped", None) is not None for effect in upgrade.results._normalize_effects())

    def _contribution_calculator(self, target: ContributionTarget = "total_dps") -> ContributionCalculator:
        if target not in CONTRIBUTION_TARGETS: raise ValueError(f"unsupported contribution target {target!r}; expected one of {sorted(CONTRIBUTION_TARGETS)}")
        return ContributionCalculator(upgrades=list(self.weapon.build), weapon_data=self.weapon.data, resolved_evolutions=self._resolved_evolutions(), metric_for_build=lambda build, evolutions, upgrades: self._metric_for_build(build, evolutions, target, list(upgrades)), upgrade_depends_on_equipped=self._upgrade_depends_on_equipped)

    def removal_contributions(self, target: ContributionTarget = "total_dps") -> dict[str, float]:
        if not self.weapon.build: return {}
        return self._contribution_calculator(target).removal_contributions()

    def shapley_contributions(self, target: ContributionTarget = "total_dps") -> dict[str, float]:
        if not self.weapon.build: return {}
        return self._contribution_calculator(target).shapley_contributions()
