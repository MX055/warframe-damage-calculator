from __future__ import annotations

import math

from ..domain.results import CalculationResult


def balanced_damage(direct: float, dot: float, balance_bonus: float = 0.1) -> float:
    direct = max(float(direct), 0.0)
    dot = max(float(dot), 0.0)
    total = direct + dot
    if total == 0: return 0.0
    balance = 2 * math.sqrt(direct * dot) / total
    return total * (1 + balance_bonus * balance)


def balanced_damage_components(direct_dph: float, dot_dph: float, direct_dps: float, dot_dps: float, damage_mass: float) -> float:
    dps = balanced_damage(direct_dps, dot_dps)
    dph = balanced_damage(direct_dph, dot_dph)
    if dps <= 0 or dph <= 0 or damage_mass <= 0: return 0.0
    return (dps * dph * damage_mass) ** (1 / 3)


def balanced_damage_metric(result: CalculationResult) -> float:
    damage = result.aggregate.damage
    total_dph = damage.direct_dph + damage.dot_dph
    weighted_damage_mass = sum((attack.damage.direct_dph + attack.damage.dot_dph) * (attack.spatial.damage_mass if attack.spatial.damage_mass is not None else 1.0) for attack in result.attacks.values())
    damage_mass = weighted_damage_mass / total_dph if total_dph > 0 else 1.0
    return balanced_damage_components(damage.direct_dph, damage.dot_dph, damage.direct_dps, damage.dot_dps, damage_mass)
