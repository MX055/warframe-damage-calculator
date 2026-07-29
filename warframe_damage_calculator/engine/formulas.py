from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..domain.damage import Dist


DOT_MULTIPLIERS = {"slash": 0.35, "heat": 0.5, "toxin": 0.5, "electricity": 0.5, "gas": 0.5}


def clamp(value: float, minimum: float | None = None, maximum: float | None = None) -> float:
    if minimum is not None: value = max(value, minimum)
    if maximum is not None: value = min(value, maximum)
    return value


def true_round(value: float, decimals: int = 0) -> float:
    quantum = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def family_factor(build: object, stat: str) -> float:
    factor = 1.0
    for family in getattr(build, "families", {}).values(): factor *= max(1 + float(family.get(stat, 0)), 1)
    return factor


def family_bonus(build: object, family: str, stat: str) -> float:
    return float(getattr(build, "families", {}).get(family, {}).get(stat, 0))


def crit_multiplier(chance: float, damage: float) -> float:
    return 1 + chance * (damage - 1)


def hit_multiplier(chance: float, damage: float, non_crit_damage: float = 0, non_crit_chance: float = 0) -> float:
    non_crit_bonus = non_crit_damage * (non_crit_chance if non_crit_chance else 1)
    return crit_multiplier(chance, damage) + max(0, 1 - chance) * non_crit_bonus


def distribute_flat(damage: Dist, value: float) -> Dist:
    return Dist({kind: value * damage.weight(kind) for kind in damage})


def refresh_metrics(metrics: object) -> None:
    rate = float(getattr(metrics, "fire_rate"))
    for prefix in ("", "weakpoint_", "resistant_"):
        direct = getattr(metrics, f"flat_{prefix}dph")
        dot = getattr(metrics, f"flat_{prefix}dotph")
        if direct is None or dot is None:
            for suffix in ("dph", "dotph", "dps", "dotps"):
                setattr(metrics, f"flat_{prefix}{suffix}", None)
            setattr(metrics, f"total_{prefix}dph", None)
            setattr(metrics, f"total_{prefix}dps", None)
            continue
        setattr(metrics, f"flat_{prefix}dps", direct * rate)
        setattr(metrics, f"flat_{prefix}dotps", dot * rate)
        setattr(metrics, f"total_{prefix}dph", direct + dot)
        setattr(metrics, f"total_{prefix}dps", (direct + dot) * rate)
