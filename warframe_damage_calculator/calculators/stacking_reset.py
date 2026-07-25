"""Stacking-reset engines (Secondary Enervate)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .effect_schema import BEHAVIOUR_STACK_RESET_CRIT_2_PLUS, ENERVATE_RESET_CHARGES_MAX
from .special_effects import iter_deferred


def enervate_params(*sources: Sequence[Mapping[str, Any]] | None) -> tuple[float, float]:
    """Return (per_stack_crit_chance, reset_charges)."""
    per_stack = 0.0
    charges = 0.0
    for entry in iter_deferred(*sources):
        if entry.get("behaviour") != BEHAVIOUR_STACK_RESET_CRIT_2_PLUS: continue
        per_stack += float(entry.get("value") or 0)
        charges = max(charges, float(entry.get("after") or entry.get("after_max") or ENERVATE_RESET_CHARGES_MAX))
    return per_stack, charges


def average_enervate_bonus(crit_chance: float, *, per_stack: float, reset_charges: float, max_stacks: int = 500) -> float:
    rate = int(reset_charges)
    if rate <= 0 or per_stack == 0: return 0.0
    length = [[0.0] * rate for _ in range(max_stacks + 1)]
    accumulated = [[0.0] * rate for _ in range(max_stacks + 1)]

    probability = max(0.0, min(1.0, crit_chance + per_stack * max_stacks - 1))
    miss = 1.0 - probability
    if miss == 1.0: return float("inf")

    length[max_stacks][rate - 1] = 1.0 / (1.0 - miss)
    accumulated[max_stacks][rate - 1] = max_stacks / (1.0 - miss)
    for index in range(rate - 2, -1, -1):
        length[max_stacks][index] = (1.0 + probability * length[max_stacks][index + 1]) / (1.0 - miss)
        accumulated[max_stacks][index] = (max_stacks + probability * accumulated[max_stacks][index + 1]) / (1.0 - miss)

    for stack in range(max_stacks - 1, -1, -1):
        probability = max(0.0, min(1.0, crit_chance + per_stack * stack - 1))
        miss = 1.0 - probability
        length[stack][rate - 1] = 1.0 + miss * length[stack + 1][rate - 1]
        accumulated[stack][rate - 1] = stack + miss * accumulated[stack + 1][rate - 1]
        for index in range(rate - 2, -1, -1):
            length[stack][index] = 1.0 + miss * length[stack + 1][index] + probability * length[stack + 1][index + 1]
            accumulated[stack][index] = stack + miss * accumulated[stack + 1][index] + probability * accumulated[stack + 1][index + 1]

    return per_stack * accumulated[0][0] / length[0][0]
