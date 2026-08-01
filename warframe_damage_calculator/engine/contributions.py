from __future__ import annotations

from collections.abc import Callable
from random import Random

from ..domain.loadouts import Loadout, Progenitor
from ..domain.results import ContributionResult
from ..domain.upgrades import Arcane, Mod, Perk, Upgrade


type ContributionComponent = Upgrade | Progenitor


_PERMUTATION_SAMPLES = 64


def progenitor_component_name(progenitor: Progenitor) -> str:
    return f"{progenitor.element.replace('_', ' ').title()} Progenitor ({progenitor.bonus:.0%})"


def component_name(component: ContributionComponent) -> str:
    return progenitor_component_name(component) if isinstance(component, Progenitor) else component.name


def _components(loadout: Loadout) -> list[ContributionComponent]:
    components: list[ContributionComponent] = [*loadout.upgrades]
    if loadout.progenitor is not None: components.append(loadout.progenitor)
    return components


def _coalition_loadout(components: list[ContributionComponent], mask: int) -> Loadout:
    selected = [component for index, component in enumerate(components) if mask & (1 << index)]
    return Loadout(mods=[component for component in selected if isinstance(component, Mod)], arcanes=[component for component in selected if isinstance(component, Arcane)], evolutions=[component for component in selected if isinstance(component, Perk)], progenitor=next((component for component in selected if isinstance(component, Progenitor)), None))


def _normalize_shapley(values: dict[str, float], total: float) -> dict[str, float]:
    difference = total - sum(values.values())
    if values and abs(difference) > 1e-9: values[next(iter(values))] += difference
    denominator = sum(values.values())
    return {name: value / denominator for name, value in values.items()} if denominator else {name: 0.0 for name in values}


def _sample_count(component_count: int) -> int:
    return 0 if component_count == 0 else _PERMUTATION_SAMPLES


def _sample_shapley(components: list[ContributionComponent], coalition_value: Callable[[int], float], seed: int) -> tuple[dict[str, float], int]:
    size = len(components)
    target_samples = _sample_count(size)
    values = {component_name(component): 0.0 for component in components}
    random = Random(seed)
    samples = 0
    while samples < target_samples:
        permutation = list(range(size))
        random.shuffle(permutation)
        for order in (permutation, reversed(permutation)):
            if samples >= target_samples: break
            mask = 0
            previous = coalition_value(mask)
            for index in order:
                mask |= 1 << index
                current = coalition_value(mask)
                values[component_name(components[index])] += current - previous
                previous = current
            samples += 1
    return {name: value / samples for name, value in values.items()}, samples


def calculate_contributions(loadout: Loadout, evaluate: Callable[[Loadout], float], seed: int = 0) -> ContributionResult:
    components = _components(loadout)
    if not components: return ContributionResult({}, {}, 0, 0)
    size = len(components)
    full_mask = (1 << size) - 1
    coalition_values: dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in coalition_values: coalition_values[mask] = evaluate(_coalition_loadout(components, mask))
        return coalition_values[mask]

    empty = coalition_value(0)
    full = coalition_value(full_mask)
    values, samples = _sample_shapley(components, coalition_value, seed)
    shapley = _normalize_shapley(values, full - empty)
    removal = {component_name(component): coalition_value(full_mask ^ (1 << index)) - full for index, component in enumerate(components)}
    return ContributionResult(shapley, removal, len(coalition_values), samples)
