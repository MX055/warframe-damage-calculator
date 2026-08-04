from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from ..domain.enemies import Enemy
from ..domain.builds import Build
from ..domain.perks import ResolvedPerk
from ..domain.results import CalculationResult, ContributionResult
from ..domain.state import ALLOWED_STATE_FIELDS, State
from ..domain.upgrades import ResolvedEffect
from ..domain.generated_attacks import GENERATED_ATTACK_STAT
from ..domain.weapons import Weapon
from .context import CalculationContext
from .contributions import calculate_contributions
from .metrics import balanced_damage_components, balanced_damage_metric
from .perks import resolve_perks
from .result_builder import build_aggregate, build_calculated_attack
from .validation import warn_build
from .weapon_calculator import WeaponCalculator, calculate_metric_components, calculate_weapon


class Calculator:
    __slots__ = ("weapon", "target", "build")

    def __init__(self, weapon: Weapon, target: Enemy | None = None, build: Build | None = None) -> None:
        self.weapon = weapon
        self.target = target
        self.build = Build() if build is None else build.copy()

    def resolve(self, *, attack: str | None = None, body_part: str | None = None, state: State | None = None) -> CalculationResult:
        selected_attack = attack or self.weapon.default_attack
        selected_body_part, target = self._select_body_part(body_part)
        return self._calculate(selected_attack, selected_body_part, target, State() if state is None else State._from_values(state))

    def contributions(self, *, attack: str | None = None, body_part: str | None = None, state: State | None = None, metric: Callable[[CalculationResult], float] = balanced_damage_metric) -> ContributionResult:
        if not callable(metric): raise TypeError("metric must be callable")
        selected_attack = attack or self.weapon.default_attack
        selected_body_part, target = self._select_body_part(body_part)
        calculation_state = State() if state is None else State._from_values(state)
        evaluator = Calculator(self.weapon, self.target)
        compact_metric = balanced_damage_components if metric is balanced_damage_metric else None
        effect_cache: dict[int, tuple[ResolvedEffect, ...]] = {}
        for upgrade in self.build.ranked_upgrades:
            if upgrade.implemented: effect_cache[id(upgrade)] = upgrade.resolve_manual()
        perk_cache: dict[tuple[int, ...], tuple[ResolvedPerk, ...]] = {}
        has_generated = any(GENERATED_ATTACK_STAT in upgrade.stats for upgrade in self.build.ranked_upgrades)
        prepared_names = None
        if not has_generated:
            baseline_perks = resolve_perks(self.weapon, self.build.evolutions)
            perk_cache[tuple(id(perk) for perk in self.build.evolutions)] = baseline_perks
            evaluator.build = self.build
            prepared_names = tuple(WeaponCalculator(CalculationContext(weapon=self.weapon, target=target, attack=selected_attack, build=self.build, resolved_perks=baseline_perks, state=self._merge_state(calculation_state))).collect_attack_tree())

        def compiled_upgrade_effects(build: Build) -> tuple[ResolvedEffect, ...]:
            effects: list[ResolvedEffect] = []
            for upgrade in build.ranked_upgrades:
                if not upgrade.implemented: continue
                cached = effect_cache.get(id(upgrade))
                if cached is None:
                    cached = upgrade.resolve_manual()
                    effect_cache[id(upgrade)] = cached
                effects.extend(cached)
            return tuple(effects)

        def evaluate(build: Build) -> float:
            evaluator.build = build
            perk_key = tuple(id(perk) for perk in build.evolutions)
            resolved_perks = perk_cache.get(perk_key)
            if resolved_perks is None:
                resolved_perks = resolve_perks(self.weapon, build.evolutions)
                perk_cache[perk_key] = resolved_perks
            upgrade_effects = compiled_upgrade_effects(build)
            if compact_metric is not None:
                return float(compact_metric(*evaluator._calculate_metric_components(selected_attack, target, calculation_state, resolved_perks=resolved_perks, prepared_names=prepared_names, prepared_upgrade_effects=upgrade_effects)))
            result = evaluator._calculate(selected_attack, selected_body_part, target, calculation_state, copy_inputs=False, resolved_perks=resolved_perks, validate=False, prepared_names=prepared_names, prepared_upgrade_effects=upgrade_effects)
            return float(metric(result))

        return calculate_contributions(self.build, evaluate)

    def _select_body_part(self, body_part: str | None) -> tuple[str, Enemy | None]:
        if self.target is None:
            if body_part not in (None, "body"): raise ValueError(f"unknown body part {body_part!r}")
            return "body", None
        selected = body_part or next(iter(self.target.body_parts))
        if selected not in self.target.body_parts: raise ValueError(f"unknown body part {selected!r}")
        target = self.target.copy()
        target.body_parts = {selected: target.body_parts[selected]}
        return selected, target

    def _merge_state(self, state: State) -> State:
        allowed = frozenset(self.weapon.calculation_defaults) | {"combo_multiplier"}
        unknown = set(state) - allowed
        if unknown: raise TypeError(f"unknown calculation state fields: {', '.join(sorted(unknown))}")
        unknown_defaults = set(self.weapon.calculation_defaults) - ALLOWED_STATE_FIELDS
        if unknown_defaults: raise TypeError(f"unknown calculation state fields: {', '.join(sorted(unknown_defaults))}")
        return State._from_values(dict(self.weapon.calculation_defaults) | dict(state))

    def _calculate_metric_components(self, selected_attack: str, target: Enemy | None, state: State, *, resolved_perks: tuple[ResolvedPerk, ...], prepared_names: tuple[str, ...] | None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[float, float, float, float, float]:
        calculation_state = self._merge_state(state)
        context = CalculationContext(weapon=self.weapon, target=target, attack=selected_attack, build=self.build, resolved_perks=resolved_perks, state=calculation_state)
        return calculate_metric_components(context, prepared_names, prepared_upgrade_effects)

    def _calculate_raw(self, selected_attack: str, target: Enemy | None, state: State, *, copy_inputs: bool = True, resolved_perks: tuple[ResolvedPerk, ...] | None = None, validate: bool = True, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None):
        generated_attacks = {WeaponCalculator._generated_key(effect) for upgrade in self.build.ranked_upgrades if upgrade.implemented for effect in upgrade.resolve_manual() if effect.stat == GENERATED_ATTACK_STAT}
        if selected_attack not in self.weapon.attacks and selected_attack not in generated_attacks: raise ValueError(f"unknown attack {selected_attack!r}")
        calculation_state = self._merge_state(state)
        resolved_perks = resolve_perks(self.weapon, self.build.evolutions) if resolved_perks is None else resolved_perks
        if validate: warn_build(self.weapon, self.build)
        context_target = target.copy() if copy_inputs and target is not None else target
        context_build = self.build.copy() if copy_inputs else self.build
        context = CalculationContext(weapon=self.weapon, target=context_target, attack=selected_attack, build=context_build, resolved_perks=resolved_perks, state=calculation_state)
        return calculate_weapon(context, prepared_names, prepared_upgrade_effects)

    def _calculate(self, selected_attack: str, selected_body_part: str, target: Enemy | None, state: State, *, copy_inputs: bool = True, resolved_perks: tuple[ResolvedPerk, ...] | None = None, validate: bool = True, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> CalculationResult:
        calculated, aggregate, aggregate_status_model, aggregate_status_effects = self._calculate_raw(selected_attack, target, state, copy_inputs=copy_inputs, resolved_perks=resolved_perks, validate=validate, prepared_names=prepared_names, prepared_upgrade_effects=prepared_upgrade_effects)
        attacks = {name: build_calculated_attack(result) for name, result in calculated.items()}
        result_weapon = self.weapon.copy() if copy_inputs else self.weapon
        if copy_inputs:
            for name, result in calculated.items(): result_weapon.attacks[name] = deepcopy(result.attack)
        result_target = None if self.target is None else self.target.copy() if copy_inputs else target
        result_build = self.build.copy() if copy_inputs else self.build
        return CalculationResult(build_aggregate(aggregate, aggregate_status_model, aggregate_status_effects), attacks, selected_attack, selected_body_part, result_weapon, result_target, result_build, State._from_values(state))
