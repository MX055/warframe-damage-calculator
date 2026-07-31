from __future__ import annotations

from collections.abc import Callable, Mapping
from math import factorial

from ..domain.loadouts import Loadout, Progenitor
from ..domain.perks import Perk
from ..domain.results import CalculationResult
from ..domain.upgrades import Upgrade
from ..engine.calculator import Calculator


type Metric = str | Callable[[CalculationResult], float]
type BodyPart = str
type ContributionComponent = Upgrade | Perk | Progenitor


def progenitor_component_name(progenitor: Progenitor) -> str:
    return f"{progenitor.element.replace('_', ' ').title()} Progenitor ({progenitor.bonus:.0%})"


def component_name(component: ContributionComponent) -> str:
    return progenitor_component_name(component) if isinstance(component, Progenitor) else component.name


def metric_value(result: CalculationResult, metric: Metric = "total_dps") -> float:
    if callable(metric): return float(metric(result))
    if "." not in metric: return float(getattr(result.aggregate.average, metric))
    value: object = result
    for name in metric.split("."): value = getattr(value, name)
    return float(value)


def _evaluate(calculator: Calculator, loadout: Loadout, attack: str, metric: Metric, bodypart: BodyPart | None, state: Mapping[str, object]) -> float:
    result = Calculator(calculator.weapon, calculator.target, loadout).calculate(attack=attack, bodypart=bodypart, state=state)
    return metric_value(result, metric)

def removal_contributions(calculator: Calculator, loadout: Loadout, *, attack: str | None = None, metric: Metric = "total_dps", bodypart: BodyPart | None = None, state: Mapping[str, object] | None = None) -> dict[str, float]:
    selected = attack or calculator.weapon.default_attack
    state = state or {}
    baseline = _evaluate(calculator, loadout, selected, metric, bodypart, state)
    contributions = {upgrade.name: _evaluate(calculator, Loadout(upgrades=[candidate for candidate in loadout.upgrades if candidate is not upgrade], evolutions=loadout.evolutions, progenitor=loadout.progenitor), selected, metric, bodypart, state) - baseline for upgrade in loadout.upgrades}
    contributions.update({perk.name: _evaluate(calculator, Loadout(upgrades=loadout.upgrades, evolutions=[candidate for candidate in loadout.evolutions if candidate != perk], progenitor=loadout.progenitor), selected, metric, bodypart, state) - baseline for perk in loadout.evolutions})
    if loadout.progenitor is not None: contributions[progenitor_component_name(loadout.progenitor)] = _evaluate(calculator, Loadout(upgrades=loadout.upgrades, evolutions=loadout.evolutions), selected, metric, bodypart, state) - baseline
    return contributions


def shapley_contributions(calculator: Calculator, loadout: Loadout, *, attack: str | None = None, metric: Metric = "total_dps", bodypart: BodyPart | None = None, state: Mapping[str, object] | None = None) -> dict[str, float]:
    selected = attack or calculator.weapon.default_attack
    state = state or {}
    components: list[ContributionComponent] = [*loadout.upgrades, *loadout.evolutions]
    if loadout.progenitor is not None: components.append(loadout.progenitor)
    size = len(components)
    if not size: return {}
    coalition_values: dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in coalition_values:
            selected_components = [component for index, component in enumerate(components) if mask & (1 << index)]
            candidate = Loadout(upgrades=[component for component in selected_components if isinstance(component, Upgrade)], evolutions=[component for component in selected_components if isinstance(component, Perk)], progenitor=next((component for component in selected_components if isinstance(component, Progenitor)), None))
            coalition_values[mask] = _evaluate(calculator, candidate, selected, metric, bodypart, state)
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
