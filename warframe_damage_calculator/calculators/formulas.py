"""Shared combat math used across calculator phases."""

from __future__ import annotations

from collections.abc import Mapping

from ..fields.calculated import AverageStats
from ..core.data import Data
from ..core.dist import Dist
from ..utils.types import Number


def crit_multiplier(crit_chance: Number, crit_damage: Number) -> float:
    return 1 + crit_chance * (crit_damage - 1)


def fold_multiplicative_families(*sources: object, stat: str = "damage_bonus") -> float:
    """Product of (1 + sum) across named families. Same family adds; different multiply."""
    from .effect_schema import FOLD_EXCLUDED_FAMILIES

    by_family: dict[str, float] = {}
    for source in sources:
        if source is None: continue
        families = getattr(source, "multiplicative_families", None) or {}
        if not isinstance(families, Mapping): continue
        for key, mode_stats in families.items():
            name = str(key)
            if name in FOLD_EXCLUDED_FAMILIES: continue
            if isinstance(mode_stats, Mapping) and not isinstance(mode_stats, Data):
                value = mode_stats.get(stat, 0)
            else:
                value = getattr(mode_stats, stat, 0) if mode_stats is not None else 0
            by_family[name] = by_family.get(name, 0.0) + float(value or 0)
    factor = 1.0
    for name in sorted(by_family):
        factor *= max(1.0 + by_family[name], 1.0)
    return factor


def family_bonus(*sources: object, family: str, stat: str = "damage_bonus") -> float:
    """Sum of one named family across sources (not folded with others)."""
    total = 0.0
    for source in sources:
        if source is None: continue
        families = getattr(source, "multiplicative_families", None) or {}
        if not isinstance(families, Mapping): continue
        mode_stats = families.get(family)
        if mode_stats is None: continue
        if isinstance(mode_stats, Mapping) and not isinstance(mode_stats, Data):
            value = mode_stats.get(stat, 0)
        else:
            value = getattr(mode_stats, stat, 0) if mode_stats is not None else 0
        total += float(value or 0)
    return total


def non_crit_bonus(damage: Number = 0, chance: Number = 0) -> float:
    damage = float(damage or 0)
    if not damage: return 0.0
    chance = float(chance or 0)
    return damage * (chance if chance else 1.0)


def multishot_consumes_ammo_enabled(*sources: object) -> bool:
    from .effect_schema import MULTISHOT_AMMO_FAMILY

    for source in sources:
        if source is None: continue
        families = getattr(source, "multiplicative_families", None) or {}
        if isinstance(families, Mapping) and MULTISHOT_AMMO_FAMILY in families: return True
    return False


def multishot_consumes_ammo_bonus(*sources: object) -> float:
    from .effect_schema import MULTISHOT_AMMO_FAMILY

    return family_bonus(*sources, family=MULTISHOT_AMMO_FAMILY, stat="damage_bonus")


def multishot_ammo_cost(ammo_cost: Number, multishot: Number, *, enabled: bool) -> float:
    cost = max(float(ammo_cost or 0), 0.0)
    if not enabled: return cost
    return cost * max(float(multishot or 1), 1.0)


def multishot_ammo_damage_factor(multishot: Number, bonus: Number) -> float:
    """Expected damage factor when a unique bonus applies only to multishot-generated pellets."""
    ms = max(float(multishot or 1), 1.0)
    value = max(float(bonus or 0), 0.0)
    if not value: return 1.0
    return 1.0 + value * (1.0 - 1.0 / ms)


def hit_multiplier(crit_chance: Number, crit_damage: Number, non_crit_bonus_damage: Number = 0, non_crit_bonus_chance: Number = 0) -> float:
    bonus = non_crit_bonus(non_crit_bonus_damage, non_crit_bonus_chance)
    return crit_multiplier(crit_chance, crit_damage) + max(0.0, 1.0 - float(crit_chance)) * bonus


def combine_chance(scaled: Number, family_factor: Number = 1, flat: Number = 0) -> Number:
    return max(scaled * family_factor + flat, 0)


def refresh_dps_from_dph(average: AverageStats) -> None:
    average.flat_dps = average.fire_rate * average.flat_dph
    average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
    average.flat_resistant_dph = average.get("flat_resistant_dph", 0)
    average.flat_resistant_dotph = average.get("flat_resistant_dotph", 0)
    average.flat_resistant_dotps = average.fire_rate * average.flat_resistant_dotph
    average.flat_resistant_dps = average.fire_rate * average.flat_resistant_dph
    average.total_dph = average.flat_dph + average.flat_dotph
    average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
    average.total_resistant_dph = average.flat_resistant_dph + average.flat_resistant_dotph
    average.total_dps = average.flat_dps + average.flat_dotps
    average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps
    average.total_resistant_dps = average.flat_resistant_dps + average.flat_resistant_dotps


def distribute_flat_damage(damage: Dist, flat: Number) -> Dist:
    return Dist({damage_type: flat * damage.weight(damage_type) for damage_type, _ in damage})
