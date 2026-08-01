from __future__ import annotations

from ..domain.status import StatusModel
from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack
from .aggregation import merge
from .automatic import automatic_value
from .context import CalculationContext
from .effects import evaluate
from .formulas import family_factor
from .models.stats import ResolvedStats, Stats


POSITION_EVENTS = frozenset({"magazine_first_shot", "magazine_last_shot"})


def _scalar(base: float, stat: str, modifiers: ResolvedStats, *, minimum: float = 0) -> float:
    value = (base + float(modifiers.base.get(stat, 0))) * (1 + float(modifiers.proportional.get(stat, 0)))
    return max(value * family_factor(modifiers, stat) + float(modifiers.flat.get(stat, 0)), minimum)


def _additive_scalar(base: float, stat: str, modifiers: ResolvedStats, *, minimum: float = 0) -> float:
    return max(base + float(modifiers.proportional.get(stat, 0)) + float(modifiers.base.get(stat, 0)) + float(modifiers.flat.get(stat, 0)), minimum)


def _combined(upgrades: ResolvedStats, evolutions: ResolvedStats) -> ResolvedStats:
    total = ResolvedStats()
    merge(total, upgrades)
    merge(total, evolutions)
    return total


def _resolve_effects(context: CalculationContext, attack: Attack, source: tuple[ResolvedEffect, ...], provisional: Stats, model: StatusModel, equipped: set[str]) -> tuple[list[ResolvedEffect], list[ResolvedEffect]]:
    resolved: list[ResolvedEffect] = []
    positions: list[ResolvedEffect] = []
    for effect in source:
        if not effect.automatic:
            resolved.append(effect)
            continue
        current = evaluate(effect, context=context, attack=attack, stats=provisional, status=model, equipped=equipped)
        if current is None: continue
        event = automatic_value(current, "on")
        if event in POSITION_EVENTS:
            positions.append(current)
        else:
            resolved.append(current)
    return resolved, positions
