from math import pi

from ..domain.weapons import Attack
from .models.attack import AverageAttackStats, SpatialMetrics
from .models.stats import EffectiveAttackStats
from .rates import SLAM_CATEGORIES


def cumulative_falloff(distance: float, start_range: float, end_range: float, final_multiplier: float) -> float:
    distance = max(distance, 0)
    if distance <= start_range: return distance
    if end_range <= start_range: return distance if distance <= end_range else end_range + final_multiplier * (distance - end_range)
    if distance <= end_range: return distance - (1 - final_multiplier) * (distance - start_range) ** 2 / (2 * (end_range - start_range))
    return final_multiplier * distance + (1 - final_multiplier) * (end_range + start_range) / 2


def average_falloff_multiplier(start_range: float, end_range: float, final_multiplier: float) -> float:
    if end_range <= 0: return 1.0
    return cumulative_falloff(end_range, start_range, end_range, final_multiplier) / end_range


def ranged_falloff_multiplier(start_range: float, end_range: float, max_range: float, final_multiplier: float) -> float:
    if max_range <= 0: return 1.0
    return cumulative_falloff(max_range, start_range, end_range, final_multiplier) / max_range


def aoe_damage_mass(start_range: float, end_range: float, final_multiplier: float) -> float:
    return 4 / 3 * pi * end_range ** 3 - pi / 3 * (1 - final_multiplier) * (end_range - start_range) * (3 * end_range ** 2 + 2 * end_range * start_range + start_range ** 2)


def is_aoe_attack(attack: Attack) -> bool:
    return bool(attack.aoe or attack.category in SLAM_CATEGORIES)


def spatial_falloff(attack: Attack, effective: EffectiveAttackStats) -> tuple[float, SpatialMetrics]:
    falloff = attack.stats.falloff
    start_range = float(effective.start_range)
    end_range = float(effective.end_range)
    max_range = effective.max_range
    final_multiplier = float(effective.final_multiplier)
    if is_aoe_attack(attack):
        if "end_range" not in falloff: return 1.0, SpatialMetrics()
        falloff_multiplier = average_falloff_multiplier(start_range, end_range, final_multiplier)
        damage_mass = aoe_damage_mass(start_range, end_range, final_multiplier)
        return falloff_multiplier, SpatialMetrics(falloff_multiplier=falloff_multiplier, damage_mass=damage_mass, dimension=3)
    falloff_multiplier = ranged_falloff_multiplier(start_range, end_range, float(max_range), final_multiplier) if max_range is not None and "end_range" in falloff else 1.0
    return falloff_multiplier, SpatialMetrics(falloff_multiplier=falloff_multiplier)


def set_damage(average: AverageAttackStats, spatial: SpatialMetrics, direct: float, dot: float) -> None:
    average_direct = direct * average.falloff_multiplier
    average_dot = dot * average.falloff_multiplier
    average.flat_dph = average_direct
    average.flat_dotph = average_dot
    if spatial.damage_mass is None:
        spatial.flat_dph = None
        spatial.flat_dotph = None
    else:
        spatial.flat_dph = direct * spatial.damage_mass
        spatial.flat_dotph = dot * spatial.damage_mass


def refresh_spatial(metrics: SpatialMetrics, fire_rate: float) -> None:
    direct, dot = metrics.flat_dph, metrics.flat_dotph
    if direct is None or dot is None:
        metrics.total_dph = metrics.flat_dps = metrics.flat_dotps = metrics.total_dps = None
        return
    metrics.total_dph = direct + dot
    metrics.flat_dps = direct * fire_rate
    metrics.flat_dotps = dot * fire_rate
    metrics.total_dps = (direct + dot) * fire_rate
