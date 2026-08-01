from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


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


def refresh_metrics(metrics: object) -> None:
    rate = float(getattr(metrics, "attack_rate"))
    direct = getattr(metrics, "flat_dph")
    dot = getattr(metrics, "flat_dotph")
    if direct is None or dot is None:
        for field in ("flat_dph", "flat_dotph", "flat_dps", "flat_dotps", "total_dph", "total_dps"): setattr(metrics, field, None)
        return
    setattr(metrics, "flat_dps", direct * rate)
    setattr(metrics, "flat_dotps", dot * rate)
    setattr(metrics, "total_dph", direct + dot)
    setattr(metrics, "total_dps", (direct + dot) * rate)
