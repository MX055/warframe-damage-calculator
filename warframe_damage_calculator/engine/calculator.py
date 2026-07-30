from __future__ import annotations

import warnings
from collections.abc import Mapping
from copy import deepcopy

from ..domain.enemies import Enemy
from ..domain.loadouts import Loadout
from ..domain.perks import Perk, ResolvedPerk
from ..domain.results import AggregateResult, AverageResult, CalculatedAttack, CalculationResult, DamageMetrics, DamageResult, SpatialDamageMetrics, SpatialResult, StatusResult, _damage_metrics
from ..domain.weapons import LoadoutCompatibilityWarning, UnimplementedUpgradeWarning, Weapon
from .context import CalculationContext
from .weapon_calculator import calculate_weapon


def _warn_loadout(weapon: Weapon, loadout: Loadout) -> None:
    previous = []
    for upgrade in loadout.upgrades:
        if not upgrade.implemented: warnings.warn(f"{upgrade.name} is not implemented and will not affect calculated results.", UnimplementedUpgradeWarning, stacklevel=3)
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


def _status(result) -> StatusResult:
    model = result.effective.status_model
    kinds = set(model.damage) | set(model.forced_procs) | set(result.status_effects)
    sustained = {kind: float(model.expected_active_stacks(kind)) for kind in kinds if model.expected_active_stacks(kind)}
    return StatusResult(float(model.expected_procs_per_attack), sustained, dict(result.status_effects))


def _spatial_metrics(source, prefix: str = "") -> SpatialDamageMetrics | None:
    direct_dph = getattr(source, f"flat_{prefix}dph" if prefix else "flat_dph")
    dot_dph = getattr(source, f"flat_{prefix}dotph" if prefix else "flat_dotph")
    total_dph = getattr(source, f"total_{prefix}dph" if prefix else "total_dph")
    direct_dps = getattr(source, f"flat_{prefix}dps" if prefix else "flat_dps")
    dot_dps = getattr(source, f"flat_{prefix}dotps" if prefix else "flat_dotps")
    total_dps = getattr(source, f"total_{prefix}dps" if prefix else "total_dps")
    if all(value is None for value in (direct_dph, dot_dph, total_dph, direct_dps, dot_dps, total_dps)): return None
    return SpatialDamageMetrics(float(direct_dph or 0), float(dot_dph or 0), float(total_dph or 0), float(direct_dps or 0), float(dot_dps or 0), float(total_dps or 0))


def _spatial(result) -> SpatialResult | None:
    spatial = result.spatial
    if spatial.dimension is None or spatial.damage_mass is None: return None
    normal = _spatial_metrics(spatial) or SpatialDamageMetrics(0, 0, 0, 0, 0, 0)
    return SpatialResult(int(spatial.dimension), float(spatial.falloff_multiplier or 1), float(spatial.damage_mass), normal, _spatial_metrics(spatial, "weakpoint_"), _spatial_metrics(spatial, "resistant_"))


def _damage_result(source) -> DamageResult:
    return DamageResult(_damage_metrics(source) or DamageMetrics(0, 0, 0, 0, 0, 0), _damage_metrics(source, "weakpoint_"), _damage_metrics(source, "resistant_"))


def _average_result(source) -> AverageResult:
    damage = _damage_result(source)
    return AverageResult(damage.normal, damage.weakpoint, damage.resistant, float(source.crit_chance), float(source.crit_multiplier), float(source.weakpoint_crit_chance), float(source.weakpoint_crit_multiplier), float(source.sustained_fire_rate), float(source.procs_per_shot), float(source.first_shot_damage_multiplier), float(source.combo_multiplier), float(source.melee_duplicate_multiplier), float(source.melee_doughty_bonus), float(source.crit_tier_bonus), float(source.weakpoint_crit_tier_bonus), float(source.secondary_enervate_bonus), float(source.weakpoint_secondary_enervate_bonus), float(source.falloff_multiplier))


def _calculated_attack(result) -> CalculatedAttack:
    return CalculatedAttack(result.name, deepcopy(result.attack), result.base, result.modded, result.effective, result.upgrades, result.evolutions, _average_result(result.average), _status(result), _spatial(result), tuple(result.children), result.original_damage)


def _aggregate(root, aggregate, attacks: dict[str, CalculatedAttack]) -> AggregateResult:
    spatial = {name: attack.spatial for name, attack in attacks.items() if attack.spatial is not None}
    return AggregateResult(root.name, _damage_result(aggregate), _status(root), spatial, tuple(attacks))


def _resolve_perks(weapon: Weapon, perks: list[Perk], state: Mapping[str, object]) -> tuple[ResolvedPerk, ...]:
    selected = list(weapon.default_perks)
    selected.extend(perk for perk in perks if perk not in selected)
    tiers: dict[int, Perk] = {}
    resolved: list[ResolvedPerk] = []
    for perk in selected:
        result = weapon.resolve_perk(perk, state=state)
        if result.tier in tiers and tiers[result.tier] != perk: raise ValueError(f"multiple evolution perks selected for tier {result.tier}")
        tiers[result.tier] = perk
        resolved.append(result)
    return tuple(resolved)


class PreparedCalculator:
    __slots__ = ("weapon", "target", "attack", "attack_names")

    def __init__(self, weapon: Weapon, target: Enemy | None, attack: str, attack_names: tuple[str, ...]) -> None:
        self.weapon = weapon
        self.target = target
        self.attack = attack
        self.attack_names = attack_names

    def calculate(self, loadout: Loadout | None = None, *, state: Mapping[str, object] | None = None) -> CalculationResult:
        return Calculator(self.weapon, self.target)._calculate(loadout, self.attack, self.attack_names, state or {})


class Calculator:
    __slots__ = ("weapon", "target")

    def __init__(self, weapon: Weapon, target: Enemy | None = None) -> None:
        self.weapon = weapon
        self.target = target

    def prepare(self, *, attack: str | None = None) -> PreparedCalculator:
        selected = attack or self.weapon.default_attack
        if selected not in self.weapon.attacks: raise ValueError(f"unknown attack {selected!r}")
        ordered: list[str] = []

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            if name not in self.weapon.attacks: raise ValueError(f"unknown child attack {name!r}")
            if name in ordered: return
            ordered.append(name)
            for child in self.weapon.attacks[name].children: collect(child, path | {name})

        collect(selected)
        return PreparedCalculator(self.weapon, self.target, selected, tuple(ordered))

    def calculate(self, loadout: Loadout | None = None, *, attack: str | None = None, state: Mapping[str, object] | None = None) -> CalculationResult:
        selected = attack or self.weapon.default_attack
        return self._calculate(loadout, selected, None, state or {})

    def _calculate(self, loadout: Loadout | None, selected: str, prepared_names: tuple[str, ...] | None, state: Mapping[str, object]) -> CalculationResult:
        loadout = Loadout() if loadout is None else loadout.copy()
        if selected not in self.weapon.attacks: raise ValueError(f"unknown attack {selected!r}")
        unknown = set(state) - set(self.weapon.calculation_defaults)
        if unknown: raise TypeError(f"unknown calculation state fields: {', '.join(sorted(unknown))}")
        calculation_state = dict(self.weapon.calculation_defaults) | dict(state)
        resolved_perks = _resolve_perks(self.weapon, loadout.evolutions, calculation_state)
        _warn_loadout(self.weapon, loadout)
        context = CalculationContext(weapon=self.weapon, target=self.target.copy() if self.target is not None else Enemy(), attack=selected, loadout=loadout, resolved_perks=resolved_perks, state=calculation_state)
        calculated, aggregate = calculate_weapon(context, prepared_names)
        attacks = {name: _calculated_attack(result) for name, result in calculated.items()}
        return CalculationResult(_aggregate(calculated[selected], aggregate, attacks), attacks, selected, self.weapon.copy(), None if self.target is None else self.target.copy(), loadout.copy(), dict(state))
