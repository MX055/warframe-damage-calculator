from __future__ import annotations

from collections.abc import Callable
from math import isclose
from random import Random

from ..domain.loadouts import Loadout, Progenitor
from ..domain.results import ContributionResult
from ..domain.perks import Perk
from ..domain.upgrades import Arcane, Mod, Upgrade


type ContributionComponent = Upgrade | Progenitor


_PERMUTATION_SAMPLES = 64
_INTERACTION_TOLERANCE = 1e-9


def progenitor_component_id(progenitor: Progenitor) -> str:
    return f"{progenitor.element.replace('_', ' ').title()} Progenitor ({progenitor.bonus:.0%})"


def component_id(component: ContributionComponent) -> str:
    return progenitor_component_id(component) if isinstance(component, Progenitor) else component.name


def _components(loadout: Loadout) -> list[ContributionComponent]:
    components: list[ContributionComponent] = [*loadout.upgrades]
    if loadout.progenitor is not None: components.append(loadout.progenitor)
    return components


def _coalition_loadout(components: list[ContributionComponent], mask: int) -> Loadout:
    selected = [component for index, component in enumerate(components) if mask & (1 << index)]
    return Loadout._from_parts(mods=[component for component in selected if isinstance(component, Mod)], arcanes=[component for component in selected if isinstance(component, Arcane)], evolutions=[component for component in selected if isinstance(component, Perk)], progenitor=next((component for component in selected if isinstance(component, Progenitor)), None))


def _normalize_contributions(values: dict[str, float]) -> dict[str, float]:
    denominator = sum(values.values())
    return {name: value / denominator for name, value in values.items()} if denominator else {name: 0.0 for name in values}


def _sample_count(component_count: int) -> int:
    if component_count == 0: return 0
    if component_count <= 8: return _PERMUTATION_SAMPLES
    return max(32, _PERMUTATION_SAMPLES - 4 * (component_count - 8))


def _suppression_masks(component_count: int, coalition_value: Callable[[int], float], full_mask: int) -> list[int]:
    masks = [0] * component_count
    full = coalition_value(full_mask)
    for index in range(component_count):
        component_bit = 1 << index
        full_marginal = full - coalition_value(full_mask ^ component_bit)
        for other_index in range(component_count):
            if other_index == index: continue
            other_bit = 1 << other_index
            without_other = full_mask ^ other_bit
            marginal_without_other = coalition_value(without_other) - coalition_value(without_other ^ component_bit)
            if abs(marginal_without_other) <= abs(full_marginal) + _INTERACTION_TOLERANCE: continue
            if full_marginal != 0 and marginal_without_other * full_marginal < 0: continue
            if not isclose(marginal_without_other, full_marginal, rel_tol=1e-9, abs_tol=_INTERACTION_TOLERANCE): masks[index] |= other_bit
    return masks


def _sample_build_contributions(components: list[ContributionComponent], coalition_value: Callable[[int], float], full_mask: int, seed: int) -> tuple[dict[str, float], int]:
    size = len(components)
    target_samples = _sample_count(size)
    values = {component_id(component): 0.0 for component in components}
    suppression_masks = _suppression_masks(size, coalition_value, full_mask)
    random = Random(seed)
    samples = 0
    while samples < target_samples:
        permutation = list(range(size))
        random.shuffle(permutation)
        for order in (permutation, list(reversed(permutation))):
            if samples >= target_samples: break
            preceding_mask = 0
            for index in order:
                component_bit = 1 << index
                context_mask = suppression_masks[index]
                coalition_mask = (preceding_mask | context_mask) & ~component_bit
                previous = coalition_value(coalition_mask)
                current = coalition_value(coalition_mask | component_bit)
                values[component_id(components[index])] += current - previous
                preceding_mask |= component_bit
            samples += 1
    return ({name: value / samples for name, value in values.items()} if samples else values), samples


def calculate_contributions(loadout: Loadout, evaluate: Callable[[Loadout], float], seed: int = 0) -> ContributionResult:
    components = _components(loadout)
    if not components: return ContributionResult({}, {}, 0, 0)
    size = len(components)
    full_mask = (1 << size) - 1
    coalition_values: dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in coalition_values: coalition_values[mask] = evaluate(_coalition_loadout(components, mask))
        return coalition_values[mask]

    full = coalition_value(full_mask)
    values, samples = _sample_build_contributions(components, coalition_value, full_mask, seed)
    contribution = _normalize_contributions(values)
    removal = {component_id(component): coalition_value(full_mask ^ (1 << index)) - full for index, component in enumerate(components)}
    return ContributionResult(contribution, removal, len(coalition_values), samples)
