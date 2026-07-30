from __future__ import annotations

from math import inf

from ..domain.upgrades import ResolvedEffect
from .effects import automatic_value


def effects_for(effects: list[ResolvedEffect], *, stat: str, event: str | None = None) -> list[ResolvedEffect]:
    return [effect for effect in effects if effect.stat == stat and (event is None or automatic_value(effect, "on") == event)]


def enervate_parameters(effects: list[ResolvedEffect]) -> tuple[float, float]:
    per_stack = 0.0
    charges = 0.0
    for effect in effects_for(effects, stat="crit_reset_charges"):
        if automatic_value(effect, "when") != "critical_tier_at_least_2" or automatic_value(effect, "reset") != "at_stack_limit": continue
        per_stack += float(automatic_value(effect, "per", 0.02))
        charges = max(charges, float(effect.value))
    return per_stack, charges


def average_enervate_bonus(crit_chance: float, per_stack: float, reset_charges: float, max_stacks: int = 500) -> float:
    rate = int(reset_charges)
    if rate <= 0 or per_stack == 0: return 0.0
    length = [[0.0] * rate for _ in range(max_stacks + 1)]
    accumulated = [[0.0] * rate for _ in range(max_stacks + 1)]
    probability = max(0.0, min(1.0, crit_chance + per_stack * max_stacks - 1))
    miss = 1 - probability
    if miss == 1: return inf
    length[max_stacks][rate - 1] = 1 / (1 - miss)
    accumulated[max_stacks][rate - 1] = max_stacks / (1 - miss)
    for index in range(rate - 2, -1, -1):
        length[max_stacks][index] = (1 + probability * length[max_stacks][index + 1]) / (1 - miss)
        accumulated[max_stacks][index] = (max_stacks + probability * accumulated[max_stacks][index + 1]) / (1 - miss)
    for stack in range(max_stacks - 1, -1, -1):
        probability = max(0.0, min(1.0, crit_chance + per_stack * stack - 1))
        miss = 1 - probability
        length[stack][rate - 1] = 1 + miss * length[stack + 1][rate - 1]
        accumulated[stack][rate - 1] = stack + miss * accumulated[stack + 1][rate - 1]
        for index in range(rate - 2, -1, -1):
            length[stack][index] = 1 + miss * length[stack + 1][index] + probability * length[stack + 1][index + 1]
            accumulated[stack][index] = stack + miss * accumulated[stack + 1][index] + probability * accumulated[stack + 1][index + 1]
    return per_stack * accumulated[0][0] / length[0][0]
