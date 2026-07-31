from __future__ import annotations

import warnings
from collections.abc import Mapping

from ..domain.enemies import Enemy
from ..domain.loadouts import Loadout
from ..domain.implementation import ImplementationWarning
from ..domain.perks import Perk, ResolvedPerk
from ..domain.results import AggregateResult, AverageResult, CalculatedAttack, CalculationResult, DamageMetrics, DamageResult, SpatialDamageMetrics, SpatialResult, StatusResult, _damage_metrics
from ..domain.weapons import LoadoutCompatibilityWarning, PerkCompatibilityWarning, ProgenitorCompatibilityWarning, UnimplementedUpgradeWarning, Weapon
from .context import CalculationContext
from .weapon_calculator import calculate_weapon


def _warn_implementation(name: str, status, *, stacklevel: int = 3) -> None:
    if status.state == "implemented": return
    details = ", ".join(status.missing_features)
    warnings.warn(f"{name} implementation is {status.state}; missing features: {details}.", ImplementationWarning, stacklevel=stacklevel)


def _warn_loadout(weapon: Weapon, loadout: Loadout) -> None:
    _warn_implementation(weapon.name, weapon.implementation_status, stacklevel=4)
    previous = []
    for upgrade in loadout.upgrades:
        if not upgrade.implemented:
            _warn_implementation(upgrade.name, upgrade.implementation_status, stacklevel=4)
            if upgrade.implementation_status.state == "not_implemented": warnings.warn(f"{upgrade.name} is not implemented and may not affect calculated results.", UnimplementedUpgradeWarning, stacklevel=3)
        compatibility = upgrade.compatibility
        matches_type = not compatibility.types or weapon.type.casefold() in {value.casefold() for value in compatibility.types}
        matches_subtype = not compatibility.subtypes or weapon.subtype is not None and weapon.subtype.casefold() in {value.casefold() for value in compatibility.subtypes}
        matches_name = not compatibility.names or weapon.name.casefold() in {value.casefold() for value in compatibility.names}
        attacks = tuple(weapon.attacks.values())
        valid = matches_type and matches_subtype and matches_name
        valid = valid and (not compatibility.categories or any(attack.category in compatibility.categories for attack in attacks))
        valid = valid and (not compatibility.triggers or any(attack.trigger in compatibility.triggers for attack in attacks))
        valid = valid and (compatibility.aoe is None or any(attack.aoe is compatibility.aoe for attack in attacks))
        if not valid: warnings.warn(f"{upgrade.name} is not compatible with {weapon.name}", LoadoutCompatibilityWarning, stacklevel=3)
        conflicts = {other.name for other in previous if other.name in upgrade.conflicts or upgrade.name in other.conflicts}
        if conflicts: warnings.warn(f"{upgrade.name} conflicts with {', '.join(sorted(conflicts))}", LoadoutCompatibilityWarning, stacklevel=3)
        previous.append(upgrade)
    supports_progenitor = "progenitor" in weapon.traits
    if loadout.progenitor is not None and not supports_progenitor: warnings.warn(f"{weapon.name} does not support progenitor bonuses; the selected progenitor will be ignored.", ProgenitorCompatibilityWarning, stacklevel=3)


def _status_from_model(model, effects: Mapping[str, float]) -> StatusResult:
    kinds = set(model.damage) | set(model.forced_procs) | set(effects)
    sustained = {kind: float(model.expected_active_stacks(kind)) for kind in kinds if model.expected_active_stacks(kind)}
    return StatusResult(float(model.expected_procs_per_attack), sustained, dict(effects))


def _status(result) -> StatusResult:
    return _status_from_model(result.effective.status_model, result.status_effects)


def _spatial(result) -> SpatialResult | None:
    spatial = result.spatial
    if spatial.dimension is None or spatial.damage_mass is None: return None
    metrics = _damage_metrics(spatial) or DamageMetrics(0, 0, 0, 0, 0, 0)
    return SpatialResult(int(spatial.dimension), float(spatial.falloff_multiplier or 1), float(spatial.damage_mass), metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps)


def _damage_result(source) -> DamageResult:
    metrics = _damage_metrics(source) or DamageMetrics(0, 0, 0, 0, 0, 0)
    return DamageResult(metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps)


def _average_result(source) -> AverageResult:
    damage = _damage_result(source)
    return AverageResult(damage=source.damage, crit_chance=float(source.crit_chance), crit_damage=float(source.crit_damage), status_chance=float(source.status_chance), status_duration=float(source.status_duration), multishot=float(source.multishot), fire_rate=float(source.fire_rate), magazine_capacity=float(source.magazine_capacity), reload_time=float(source.reload_time), ammo_cost=float(source.ammo_cost), ammo_efficiency=float(source.ammo_efficiency), punch_through=float(source.punch_through), burst_count=float(source.burst_count), burst_delay=float(source.burst_delay), charge_time=float(source.charge_time), attack_speed=float(source.attack_speed), heavy_attack_speed=float(source.heavy_attack_speed), heavy_attack_efficiency=float(source.heavy_attack_efficiency), initial_combo=float(source.initial_combo), direct_dph=damage.direct_dph, dot_dph=damage.dot_dph, total_dph=damage.total_dph, direct_dps=damage.direct_dps, dot_dps=damage.dot_dps, total_dps=damage.total_dps, crit_multiplier=float(source.crit_multiplier), weakpoint_crit_chance=float(source.weakpoint_crit_chance), weakpoint_crit_multiplier=float(source.weakpoint_crit_multiplier), attacks_per_second=float(source.attacks_per_second), first_shot_damage_multiplier=float(source.first_shot_damage_multiplier), combo_multiplier=float(source.combo_multiplier), melee_duplicate_multiplier=float(source.melee_duplicate_multiplier), melee_doughty_bonus=float(source.melee_doughty_bonus), crit_tier_bonus=float(source.crit_tier_bonus), weakpoint_crit_tier_bonus=float(source.weakpoint_crit_tier_bonus), secondary_enervate_bonus=float(source.secondary_enervate_bonus), weakpoint_secondary_enervate_bonus=float(source.weakpoint_secondary_enervate_bonus), falloff_multiplier=float(source.falloff_multiplier))


def _calculated_attack(result) -> CalculatedAttack:
    return CalculatedAttack(result.base, result.modded, result.effective, result.upgrades, result.evolutions, _average_result(result.average), _status(result), _spatial(result))


def _aggregate(average, status_model, status_effects: Mapping[str, float]) -> AggregateResult:
    return AggregateResult(_damage_result(average), _status_from_model(status_model, status_effects))


def _resolve_perks(weapon: Weapon, perks: list[Perk], state: Mapping[str, object]) -> tuple[ResolvedPerk, ...]:
    selected = list(weapon.default_perks)
    selected.extend(perk for perk in perks if perk not in selected)
    tiers: dict[int, Perk] = {}
    resolved: list[ResolvedPerk] = []
    for perk in selected:
        if perk not in weapon.perks:
            warnings.warn(f"{perk.name} is not compatible with {weapon.name} and will be ignored.", PerkCompatibilityWarning, stacklevel=4)
            continue
        _warn_implementation(perk.name, perk.implementation_status, stacklevel=5)
        result = weapon.resolve_perk(perk, state=state)
        if result.tier in tiers and tiers[result.tier] != perk: raise ValueError(f"multiple evolution perks selected for tier {result.tier}")
        tiers[result.tier] = perk
        resolved.append(result)
    return tuple(resolved)


class Calculator:
    __slots__ = ("weapon", "target", "loadout")

    def __init__(self, weapon: Weapon, target: Enemy | None = None, loadout: Loadout | None = None) -> None:
        self.weapon = weapon
        self.target = target
        self.loadout = Loadout() if loadout is None else loadout.copy()

    def calculate(self, *, attack: str | None = None, bodypart: str | None = None, state: Mapping[str, object] | None = None) -> CalculationResult:
        selected_attack = attack or self.weapon.default_attack
        selected_bodypart, target = self._select_bodypart(bodypart)
        return self._calculate(selected_attack, selected_bodypart, target, state or {})

    def _select_bodypart(self, bodypart: str | None) -> tuple[str, Enemy | None]:
        if self.target is None:
            if bodypart not in (None, "body"): raise ValueError(f"unknown body part {bodypart!r}")
            return "body", None
        selected = bodypart or next(iter(self.target.bodyparts))
        if selected not in self.target.bodyparts: raise ValueError(f"unknown body part {selected!r}")
        target = self.target.copy()
        target.bodyparts = {selected: target.bodyparts[selected]}
        return selected, target

    def _calculate(self, selected_attack: str, selected_bodypart: str, target: Enemy | None, state: Mapping[str, object]) -> CalculationResult:
        if selected_attack not in self.weapon.attacks: raise ValueError(f"unknown attack {selected_attack!r}")
        unknown = set(state) - set(self.weapon.calculation_defaults)
        if unknown: raise TypeError(f"unknown calculation state fields: {', '.join(sorted(unknown))}")
        calculation_state = dict(self.weapon.calculation_defaults) | dict(state)
        resolved_perks = _resolve_perks(self.weapon, self.loadout.evolutions, calculation_state)
        _warn_loadout(self.weapon, self.loadout)
        context = CalculationContext(weapon=self.weapon, target=target.copy() if target is not None else Enemy(), attack=selected_attack, loadout=self.loadout.copy(), resolved_perks=resolved_perks, state=calculation_state)
        calculated, aggregate, aggregate_status_model, aggregate_status_effects = calculate_weapon(context)
        attacks = {name: _calculated_attack(result) for name, result in calculated.items()}
        return CalculationResult(_aggregate(aggregate, aggregate_status_model, aggregate_status_effects), attacks, selected_attack, selected_bodypart, self.weapon.copy(), None if self.target is None else self.target.copy(), self.loadout.copy(), dict(state))
