"""Aggregation policies for resolved upgrade and evolution effects.

Resolution decides which effects are active and their values.
Aggregation decides how those values combine into a stats container.

Policies are selected explicitly from registries; unknown ordinary additive
stats fall back to _merge_ordinary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..fields.evolution import ConversionBonus
from ..fields.upgrade import ResolvedStat
from ..models.data import Data
from ..models.dist import Dist
from ..utils.constants import DAMAGE_TYPES, EFFECT_MODES
from ..utils.types import Number

Aggregator = Callable[[Data, str, Any], None]


def _merge_numeric(stats: Data, stat: str, value: Any) -> None:
    current = stats.get(stat)
    stats._values[stat] = value if current is None else current + value


def _merge_boolean(stats: Data, stat: str, value: Any) -> None:
    current = stats.get(stat)
    stats._values[stat] = value if current is None else (current or value)


def _merge_mapping(stats: Data, stat: str, value: Mapping[str, Any]) -> None:
    current = stats.get(stat)
    if not isinstance(current, Mapping): current = {}
    stats[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in dict(current) | dict(value)}


def _merge_damage(stats: Data, stat: str, value: Any) -> None:
    current = stats.get(stat)
    if not isinstance(current, Dist): current = Dist(current or {})
    if not isinstance(value, Dist): value = Dist(value)
    stats._values[stat] = current + value


def _merge_condition_overload(stats: Data, stat: str, value: Mapping[str, Any]) -> None:
    current = stats.get(stat) or {}
    maximums = {current.get("max_stacks", 0), value.get("max_stacks", 0)}
    stats[stat] = {"value": current.get("value", 0) + value.get("value", 0), "max_stacks": "inf" if "inf" in maximums else max(maximums)}


def _merge_conversion(stats: Data, stat: str, value: Any, *, conversion_max: Number | None = None) -> None:
    current = stats.get(stat)
    if not isinstance(current, ConversionBonus): current = ConversionBonus()
    current.value = float(current.value) + float(value)
    if conversion_max is not None: current.max = max(float(current.max), float(conversion_max))
    stats[stat] = current


def _merge_ordinary(stats: Data, stat: str, value: Any) -> None:
    """Fallback for ordinary additive stats without a declared special policy."""
    current = stats.get(stat)
    if current is None: stats[stat] = value
    elif isinstance(value, bool): _merge_boolean(stats, stat, value)
    elif isinstance(current, Mapping) and isinstance(value, Mapping): _merge_mapping(stats, stat, value)
    else: _merge_numeric(stats, stat, value)


# Declared upgrade/build policies. Unknown stats use _merge_ordinary.
UPGRADE_AGGREGATORS: dict[str, Aggregator] = {
    "damage": _merge_damage,
    "forced_procs": _merge_damage,
    "condition_overload": _merge_condition_overload,
    "fire_rate_lock": _merge_boolean,
    "multishot_lock": _merge_boolean,
}

CONVERSION_STATS = frozenset({"crit_from_status", "status_from_crit"})

# Evolution elemental damage types become Dist entries; flat "damage" stays numeric.
EVOLUTION_AGGREGATORS: dict[str, Aggregator] = {
    "forced_procs": _merge_damage,
}


def merge_upgrade_stat(stats: Data, stat: str, value: Any) -> None:
    """Merge one upgrade effect into a mode stats container via the policy registry."""
    if stat in DAMAGE_TYPES: stat, value = "damage", {stat: value}
    aggregator = UPGRADE_AGGREGATORS.get(stat, _merge_ordinary)
    aggregator(stats, stat, value)


def merge_mode_stats(target: Data, source: Data) -> None:
    defaults = type(source)._defaults
    for stat, value in source.items():
        if stat in defaults and value == defaults[stat]: continue
        merge_upgrade_stat(target, stat, value)


def merge_resolved_stat(target: ResolvedStat, source: ResolvedStat) -> None:
    for mode in EFFECT_MODES: merge_mode_stats(getattr(target, mode), getattr(source, mode))


def merge_evolution_stat(stats: Data, stat: str, value: Any, *, conversion_max: Number | None = None) -> None:
    """Merge one evolution effect; conversion stats use ConversionBonus aggregation."""
    if stat in CONVERSION_STATS:
        _merge_conversion(stats, stat, float(value), conversion_max=conversion_max)
        return
    # Flat evolution "damage" is numeric; Dist merge is only for forced_procs and similar.
    aggregator = EVOLUTION_AGGREGATORS.get(stat, _merge_ordinary)
    aggregator(stats, stat, value)
