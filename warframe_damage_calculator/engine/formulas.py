from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from math import pi

from ..domain.damage import Dist


DOT_MULTIPLIERS = {"slash": 0.35, "heat": 0.5, "toxin": 0.5, "electricity": 0.5, "gas": 0.5}


def clamp(value: float, minimum: float | None = None, maximum: float | None = None) -> float:
    if minimum is not None: value = max(value, minimum)
    if maximum is not None: value = min(value, maximum)
    return value


def true_round(value: float, decimals: int = 0) -> float:
    quantum = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def family_factor(resolved: object, stat: str) -> float:
    factor = 1.0
    for family in getattr(resolved, "families", {}).values(): factor *= max(1 + float(family.get(stat, 0)), 1)
    return factor


def family_bonus(resolved: object, family: str, stat: str) -> float:
    return float(getattr(resolved, "families", {}).get(family, {}).get(stat, 0))


def crit_multiplier(chance: float, damage: float) -> float:
    return 1 + chance * (damage - 1)


def hit_multiplier(chance: float, damage: float, non_crit_damage: float = 0, non_crit_chance: float = 0) -> float:
    non_crit_bonus = non_crit_damage * (non_crit_chance if non_crit_chance else 1)
    return crit_multiplier(chance, damage) + max(0, 1 - chance) * non_crit_bonus


def average_falloff_multiplier(start_range: float, end_range: float, final_multiplier: float) -> float:
    if end_range <= 0: return 1.0
    return cumulative_falloff(end_range, start_range, end_range, final_multiplier) / end_range


def cumulative_falloff(distance: float, start_range: float, end_range: float, final_multiplier: float) -> float:
    distance = max(distance, 0)
    if distance <= start_range: return distance
    if end_range <= start_range: return distance if distance <= end_range else end_range + final_multiplier * (distance - end_range)
    if distance <= end_range: return distance - (1 - final_multiplier) * (distance - start_range) ** 2 / (2 * (end_range - start_range))
    return final_multiplier * distance + (1 - final_multiplier) * (end_range + start_range) / 2


def ranged_falloff_multiplier(start_range: float, end_range: float, max_range: float, final_multiplier: float) -> float:
    if max_range <= 0: return 1.0
    return cumulative_falloff(max_range, start_range, end_range, final_multiplier) / max_range


def aoe_damage_mass(start_range: float, end_range: float, final_multiplier: float) -> float:
    return 4 / 3 * pi * end_range ** 3 - pi / 3 * (1 - final_multiplier) * (end_range - start_range) * (3 * end_range ** 2 + 2 * end_range * start_range + start_range ** 2)


def distribute_flat(damage: Dist, value: float) -> Dist:
    return Dist({kind: value * damage.weight(kind) for kind in damage})


def refresh_metrics(metrics: object) -> None:
    rate = float(getattr(metrics, "sustained_fire_rate"))
    direct = getattr(metrics, "flat_dph")
    dot = getattr(metrics, "flat_dotph")
    if direct is None or dot is None:
        for field in ("flat_dph", "flat_dotph", "flat_dps", "flat_dotps", "total_dph", "total_dps"): setattr(metrics, field, None)
        return
    setattr(metrics, "flat_dps", direct * rate)
    setattr(metrics, "flat_dotps", dot * rate)
    setattr(metrics, "total_dph", direct + dot)
    setattr(metrics, "total_dps", (direct + dot) * rate)
