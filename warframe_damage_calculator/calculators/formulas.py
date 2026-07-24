"""Shared combat math used across calculator phases."""

from __future__ import annotations

from ..fields.calculated import AverageStats
from ..core.dist import Dist
from ..utils.types import Number


def crit_multiplier(crit_chance: Number, crit_damage: Number) -> float:
    return 1 + crit_chance * (crit_damage - 1)


def non_crit_bonus(damage: Number = 0, chance: Number = 0) -> float:
    damage = float(damage or 0)
    if not damage: return 0.0
    chance = float(chance or 0)
    return damage * (chance if chance else 1.0)


def hit_multiplier(crit_chance: Number, crit_damage: Number, non_crit_bonus_damage: Number = 0, non_crit_bonus_chance: Number = 0) -> float:
    bonus = non_crit_bonus(non_crit_bonus_damage, non_crit_bonus_chance)
    return crit_multiplier(crit_chance, crit_damage) + max(0.0, 1.0 - float(crit_chance)) * bonus


def combine_chance(additive: Number, multiplicative: Number = 1, flat: Number = 0) -> Number:
    return max(additive * multiplicative + flat, 0)


def refresh_dps_from_dph(average: AverageStats) -> None:
    average.flat_dps = average.fire_rate * average.flat_dph
    average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
    average.total_dph = average.flat_dph + average.flat_dotph
    average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
    average.total_dps = average.flat_dps + average.flat_dotps
    average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps


def distribute_flat_damage(damage: Dist, flat: Number) -> Dist:
    return Dist({damage_type: flat * damage.weight(damage_type) for damage_type, _ in damage})
