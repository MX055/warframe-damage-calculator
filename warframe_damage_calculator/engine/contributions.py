from __future__ import annotations

from collections.abc import Callable

from ..domain.builds import Build, Progenitor
from ..domain.results import ContributionResult
from ..domain.perks import Perk
from ..domain.upgrades import Arcane, Mod, Upgrade


type ContributionComponent = Upgrade | Progenitor


def progenitor_component_id(progenitor: Progenitor) -> str:
    return f"{progenitor.element.replace('_', ' ').title()} Progenitor ({progenitor.bonus:.0%})"


def component_id(component: ContributionComponent) -> str:
    return progenitor_component_id(component) if isinstance(component, Progenitor) else component.name


def _components(build: Build) -> list[ContributionComponent]:
    components: list[ContributionComponent] = [*build.upgrades]
    if build.progenitor is not None: components.append(build.progenitor)
    return components


def _coalition_build(components: list[ContributionComponent], mask: int) -> Build:
    selected = [component for index, component in enumerate(components) if mask & (1 << index)]
    return Build._from_parts(mods=[component for component in selected if isinstance(component, Mod)], arcanes=[component for component in selected if isinstance(component, Arcane)], evolutions=[component for component in selected if isinstance(component, Perk)], progenitor=next((component for component in selected if isinstance(component, Progenitor)), None))


def _normalize_contributions(values: dict[str, float]) -> dict[str, float]:
    denominator = sum(values.values())
    return {name: value / denominator for name, value in values.items()} if denominator else {name: 0.0 for name in values}


def calculate_contributions(build: Build, evaluate: Callable[[Build], float], seed: int = 0) -> ContributionResult:
    components = _components(build)
    if not components: return ContributionResult({}, {}, 0, 0)
    size = len(components)
    full_mask = (1 << size) - 1
    coalition_values: dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in coalition_values: coalition_values[mask] = evaluate(_coalition_build(components, mask))
        return coalition_values[mask]

    full = coalition_value(full_mask)
    removal = {component_id(component): coalition_value(full_mask ^ (1 << index)) - full for index, component in enumerate(components)}
    contribution = _normalize_contributions({name: -value for name, value in removal.items()})
    return ContributionResult(contribution, removal, len(coalition_values), 0)
