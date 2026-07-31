from __future__ import annotations

from collections.abc import Callable
from math import factorial

from ..domain.loadouts import Loadout, Progenitor
from ..domain.results import ContributionResult
from ..domain.upgrades import Arcane, Mod, Perk, Upgrade


type ContributionComponent = Upgrade | Progenitor


def progenitor_component_name(progenitor: Progenitor) -> str:
    return f"{progenitor.element.replace('_', ' ').title()} Progenitor ({progenitor.bonus:.0%})"


def component_name(component: ContributionComponent) -> str:
    return progenitor_component_name(component) if isinstance(component, Progenitor) else component.name


def _without_upgrade(loadout: Loadout, upgrade: Upgrade) -> Loadout:
    return Loadout(mods=[candidate for candidate in loadout.mods if candidate is not upgrade], arcanes=[candidate for candidate in loadout.arcanes if candidate is not upgrade], evolutions=loadout.evolutions, progenitor=loadout.progenitor)


def _without_perk(loadout: Loadout, perk: Perk) -> Loadout:
    return Loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=[candidate for candidate in loadout.evolutions if candidate != perk], progenitor=loadout.progenitor)


def _removal_contributions(loadout: Loadout, evaluate: Callable[[Loadout], float]) -> dict[str, float]:
    baseline = evaluate(loadout)
    contributions = {upgrade.name: evaluate(_without_upgrade(loadout, upgrade)) - baseline for upgrade in loadout.ranked_upgrades}
    contributions.update({perk.name: evaluate(_without_perk(loadout, perk)) - baseline for perk in loadout.evolutions})
    if loadout.progenitor is not None: contributions[progenitor_component_name(loadout.progenitor)] = evaluate(Loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions)) - baseline
    return contributions


def _shapley_contributions(loadout: Loadout, evaluate: Callable[[Loadout], float]) -> dict[str, float]:
    components: list[ContributionComponent] = [*loadout.upgrades]
    if loadout.progenitor is not None: components.append(loadout.progenitor)
    size = len(components)
    if not size: return {}
    coalition_values: dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in coalition_values:
            selected = [component for index, component in enumerate(components) if mask & (1 << index)]
            candidate = Loadout(mods=[component for component in selected if isinstance(component, Mod)], arcanes=[component for component in selected if isinstance(component, Arcane)], evolutions=[component for component in selected if isinstance(component, Perk)], progenitor=next((component for component in selected if isinstance(component, Progenitor)), None))
            coalition_values[mask] = evaluate(candidate)
        return coalition_values[mask]

    empty = coalition_value(0)
    values = {component_name(component): 0.0 for component in components}
    for index, component in enumerate(components):
        bit = 1 << index
        for mask in range(1 << size):
            if mask & bit: continue
            subset_size = mask.bit_count()
            weight = factorial(subset_size) * factorial(size - subset_size - 1) / factorial(size)
            values[component_name(component)] += weight * (coalition_value(mask | bit) - coalition_value(mask))
    total = coalition_value((1 << size) - 1) - empty
    difference = total - sum(values.values())
    if values and abs(difference) > 1e-9: values[next(iter(values))] += difference
    denominator = sum(values.values())
    return {name: value / denominator for name, value in values.items()} if denominator else {name: 0.0 for name in values}


def calculate_contributions(loadout: Loadout, evaluate: Callable[[Loadout], float]) -> ContributionResult:
    shapley = _shapley_contributions(loadout, evaluate)
    return ContributionResult(shapley, _removal_contributions(loadout, evaluate) if shapley else {})
