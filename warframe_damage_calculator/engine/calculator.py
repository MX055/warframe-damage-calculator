from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from ..domain.enemies import Enemy
from ..domain.loadouts import Loadout
from ..domain.perks import ResolvedPerk
from ..domain.results import CalculationResult, ContributionResult
from ..domain.state import State
from ..domain.upgrades import ResolvedEffect
from ..domain.generated_attacks import GENERATED_ATTACK_STAT
from ..domain.weapons import Weapon
from .context import CalculationContext
from .contributions import calculate_contributions
from .perks import resolve_perks
from .result_builder import build_aggregate, build_calculated_attack
from .validation import warn_loadout
from .weapon_calculator import WeaponCalculator, calculate_metric_components, calculate_weapon


class Calculator:
    __slots__ = ("weapon", "target", "loadout")

    def __init__(self, weapon: Weapon, target: Enemy | None = None, loadout: Loadout | None = None) -> None:
        self.weapon = weapon
        self.target = target
        self.loadout = Loadout() if loadout is None else loadout.copy()

    def resolve(self, *, attack: str | None = None, body_part: str | None = None, state: State | None = None) -> CalculationResult:
        selected_attack = attack or self.weapon.default_attack
        selected_bodypart, target = self._select_bodypart(body_part)
        return self._calculate(selected_attack, selected_bodypart, target, State() if state is None else State(state))

    def contributions(self, *, attack: str | None = None, metric: str | Callable[[CalculationResult], float] = "total_dps", body_part: str | None = None, state: State | None = None, seed: int = 0) -> ContributionResult:
        selected_attack = attack or self.weapon.default_attack
        selected_bodypart, _ = self._select_bodypart(body_part)
        calculation_state = State() if state is None else State(state)

        def evaluate(loadout: Loadout) -> float:
            result = Calculator(self.weapon, self.target, loadout).resolve(attack=selected_attack, body_part=selected_bodypart, state=calculation_state)
            if callable(metric): return float(metric(result))
            value: object = result
            for name in metric.split(".") if "." in metric else ("aggregate", "average", metric): value = getattr(value, name)
            return float(value)

        return calculate_contributions(self.loadout, evaluate, seed)

    def _select_bodypart(self, body_part: str | None) -> tuple[str, Enemy | None]:
        if self.target is None:
            if body_part not in (None, "body"): raise ValueError(f"unknown body part {body_part!r}")
            return "body", None
        selected = body_part or next(iter(self.target.bodyparts))
        if selected not in self.target.bodyparts: raise ValueError(f"unknown body part {selected!r}")
        target = self.target.copy()
        target.bodyparts = {selected: target.bodyparts[selected]}
        return selected, target

    def _calculate_metric_components(self, selected_attack: str, target: Enemy | None, state: State, *, resolved_perks: tuple[ResolvedPerk, ...], prepared_names: tuple[str, ...] | None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[float, float, float, float, float]:
        calculation_state = State(dict(self.weapon.calculation_defaults) | dict(state))
        context = CalculationContext(weapon=self.weapon, target=target if target is not None else Enemy(), attack=selected_attack, loadout=self.loadout, resolved_perks=resolved_perks, state=calculation_state)
        return calculate_metric_components(context, prepared_names, prepared_upgrade_effects)

    def _calculate_raw(self, selected_attack: str, target: Enemy | None, state: State, *, copy_inputs: bool = True, resolved_perks: tuple[ResolvedPerk, ...] | None = None, validate: bool = True, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None):
        generated_attacks = {WeaponCalculator._generated_key(effect) for upgrade in self.loadout.ranked_upgrades if upgrade.implemented for effect in upgrade.resolve_manual() if effect.stat == GENERATED_ATTACK_STAT}
        if selected_attack not in self.weapon.attacks and selected_attack not in generated_attacks: raise ValueError(f"unknown attack {selected_attack!r}")
        unknown = set(state) - set(self.weapon.calculation_defaults)
        if unknown: raise TypeError(f"unknown calculation state fields: {', '.join(sorted(unknown))}")
        calculation_state = State(dict(self.weapon.calculation_defaults) | dict(state))
        resolved_perks = resolve_perks(self.weapon, self.loadout.evolutions, calculation_state) if resolved_perks is None else resolved_perks
        if validate: warn_loadout(self.weapon, self.loadout)
        context_target = target.copy() if copy_inputs and target is not None else target if target is not None else Enemy()
        context_loadout = self.loadout.copy() if copy_inputs else self.loadout
        context = CalculationContext(weapon=self.weapon, target=context_target, attack=selected_attack, loadout=context_loadout, resolved_perks=resolved_perks, state=calculation_state)
        return calculate_weapon(context, prepared_names, prepared_upgrade_effects)

    def _calculate(self, selected_attack: str, selected_body_part: str, target: Enemy | None, state: State, *, copy_inputs: bool = True, resolved_perks: tuple[ResolvedPerk, ...] | None = None, validate: bool = True, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> CalculationResult:
        calculated, aggregate, aggregate_status_model, aggregate_status_effects = self._calculate_raw(selected_attack, target, state, copy_inputs=copy_inputs, resolved_perks=resolved_perks, validate=validate, prepared_names=prepared_names, prepared_upgrade_effects=prepared_upgrade_effects)
        attacks = {name: build_calculated_attack(result) for name, result in calculated.items()}
        result_weapon = self.weapon.copy() if copy_inputs else self.weapon
        if copy_inputs:
            for name, result in calculated.items(): result_weapon.attacks[name] = deepcopy(result.attack)
        result_target = None if self.target is None else self.target.copy() if copy_inputs else target
        result_loadout = self.loadout.copy() if copy_inputs else self.loadout
        return CalculationResult(build_aggregate(aggregate, aggregate_status_model, aggregate_status_effects), attacks, selected_attack, selected_body_part, result_weapon, result_target, result_loadout, State(state))
