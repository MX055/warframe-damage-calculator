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
    by_family: dict[str, float] = {}
    for source in sources:
        if source is None: continue
        families = getattr(source, "multiplicative_families", None) or {}
        if not isinstance(families, Mapping): continue
        for key, mode_stats in families.items():
            if isinstance(mode_stats, Mapping) and not isinstance(mode_stats, Data):
                value = mode_stats.get(stat, 0)
            else:
                value = getattr(mode_stats, stat, 0) if mode_stats is not None else 0
            name = str(key)
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


def hit_multiplier(crit_chance: Number, crit_damage: Number, non_crit_bonus_damage: Number = 0, non_crit_bonus_chance: Number = 0) -> float:
    bonus = non_crit_bonus(non_crit_bonus_damage, non_crit_bonus_chance)
    return crit_multiplier(crit_chance, crit_damage) + max(0.0, 1.0 - float(crit_chance)) * bonus


def combine_chance(scaled: Number, family_factor: Number = 1, flat: Number = 0) -> Number:
    return max(scaled * family_factor + flat, 0)


def refresh_dps_from_dph(average: AverageStats) -> None:
    average.flat_dps = average.fire_rate * average.flat_dph
    average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
    average.total_dph = average.flat_dph + average.flat_dotph
    average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
    average.total_dps = average.flat_dps + average.flat_dotps
    average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps


def distribute_flat_damage(damage: Dist, flat: Number) -> Dist:
    return Dist({damage_type: flat * damage.weight(damage_type) for damage_type, _ in damage})
