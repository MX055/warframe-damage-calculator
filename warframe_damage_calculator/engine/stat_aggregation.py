"""Aggregation policies for resolved upgrade and evolution effects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..fields.evolution_data import ConversionBonus, ResolvedEvolutionModeStats, ResolvedEvolutionStat
from ..fields.upgrade_data import ResolvedModeStats, ResolvedStat
from ..core.data import Data
from ..core.dist import Dist
from ..utils.constants import DAMAGE_TYPES, EFFECT_MODES
from ..utils.types import Number

Aggregator = Callable[[Data, str, Any], None]
DEFERRED = ("magazine_position", "stacking_reset", "application_chance", "conversions")


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


def _merge_status_effect_stacks(stats: Data, stat: str, value: Any) -> None:
    current = stats.get(stat)
    if not isinstance(current, list): current = [] if current is None else [current]
    entries = value if isinstance(value, list) else [value]
    stats[stat] = [*current, *entries]


def _merge_conversion(stats: Data, stat: str, value: Any, *, conversion_max: Number | None = None) -> None:
    current = stats.get(stat)
    if not isinstance(current, ConversionBonus): current = ConversionBonus()
    current.value = float(current.value) + float(value)
    if conversion_max is not None: current.max = max(float(current.max), float(conversion_max))
    stats[stat] = current


def _merge_noise_level(stats: Data, stat: str, value: Any) -> None:
    current = stats.get(stat)
    stats[stat] = "silent" if "silent" in (current, value) else value


def _merge_ordinary(stats: Data, stat: str, value: Any) -> None:
    current = stats.get(stat)
    if current is None: stats[stat] = value
    elif isinstance(value, bool) or isinstance(current, bool): _merge_boolean(stats, stat, value)
    elif isinstance(value, str) or isinstance(current, str): stats[stat] = value
    elif isinstance(current, Mapping) and isinstance(value, Mapping): _merge_mapping(stats, stat, value)
    else: _merge_numeric(stats, stat, value)


UPGRADE_AGGREGATORS: dict[str, Aggregator] = {
    "damage": _merge_damage,
    "forced_procs": _merge_damage,
    "condition_overload": _merge_condition_overload,
    "status_effect_stacks": _merge_status_effect_stacks,
    "fire_rate_lock": _merge_boolean,
    "multishot_lock": _merge_boolean,
    "noise_level": _merge_noise_level,
}

CONVERSION_STATS = frozenset({"crit_from_status", "status_from_crit"})

EVOLUTION_AGGREGATORS: dict[str, Aggregator] = {
    "damage_types": _merge_damage,
    "forced_procs": _merge_damage,
}


def merge_upgrade_stat(stats: Data, stat: str, value: Any) -> None:
    if stat in DAMAGE_TYPES: stat, value = "damage", {stat: value}
    aggregator = UPGRADE_AGGREGATORS.get(stat, _merge_ordinary)
    aggregator(stats, stat, value)


def merge_mode_stats(target: Data, source: Data) -> None:
    defaults = type(source)._defaults
    for stat, value in source.items():
        if stat in defaults and value == defaults[stat]: continue
        merge_upgrade_stat(target, stat, value)


def merge_multiplicative_families(target: Data, source: Data, *, mode_stats_type: type = ResolvedModeStats) -> None:
    for key, mode_stats in source.items():
        current = target.get(key)
        if not isinstance(current, mode_stats_type):
            current = mode_stats_type(current) if isinstance(current, Mapping) else mode_stats_type()
            target[key] = current
        if isinstance(mode_stats, Mapping) and not isinstance(mode_stats, mode_stats_type):
            mode_stats = mode_stats_type(mode_stats)
        merge_mode_stats(current, mode_stats)


def merge_resolved_stat(target: ResolvedStat, source: ResolvedStat) -> None:
    for mode in EFFECT_MODES: merge_mode_stats(getattr(target, mode), getattr(source, mode))
    if source.multiplicative_families:
        merge_multiplicative_families(target.multiplicative_families, source.multiplicative_families, mode_stats_type=ResolvedModeStats)
    for key in DEFERRED:
        entries = getattr(source, key, None)
        if entries: setattr(target, key, [*(getattr(target, key) or []), *entries])


def merge_resolved_evolution_stat(target: ResolvedEvolutionStat, source: ResolvedEvolutionStat) -> None:
    for mode in EFFECT_MODES: merge_mode_stats(getattr(target, mode), getattr(source, mode))
    if source.multiplicative_families:
        merge_multiplicative_families(target.multiplicative_families, source.multiplicative_families, mode_stats_type=ResolvedEvolutionModeStats)
    for key in DEFERRED:
        entries = getattr(source, key, None)
        if entries: setattr(target, key, [*(getattr(target, key) or []), *entries])


def merge_evolution_stat(stats: Data, stat: str, value: Any, *, conversion_max: Number | None = None) -> None:
    if stat in DAMAGE_TYPES: stat, value = "damage_types", {stat: value}
    if stat in CONVERSION_STATS:
        _merge_conversion(stats, stat, float(value), conversion_max=conversion_max)
        return
    aggregator = EVOLUTION_AGGREGATORS.get(stat, _merge_ordinary)
    aggregator(stats, stat, value)
