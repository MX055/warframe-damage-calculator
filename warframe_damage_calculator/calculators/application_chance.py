"""Resolve deferred application_chance / conversions entries by behavior."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .effect_schema import (
    BEHAVIOR_FROM_PUNCTURE_X_STATUS,
    BEHAVIOR_NEAR_YELLOW,
    BEHAVIOR_ON_ANY_PROC,
    BEHAVIOR_ON_CRIT,
    BEHAVIOR_ON_HIT,
    BEHAVIOR_ON_IMPACT_FR,
    DOUGHTY_PER,
    IB_FIRE_RATE_THRESHOLD,
)
from .special_effects import iter_deferred


def _entries(*sources: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    return iter_deferred(*sources)


def _behavior_data(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    data = entry.get("behavior_data")
    return data if isinstance(data, Mapping) else {}


def sum_chance(entries: Sequence[Mapping[str, Any]], *, behavior: str, stat: str | None = None) -> float:
    total = 0.0
    for entry in entries:
        if entry.get("behavior") != behavior: continue
        if stat is not None and entry.get("stat") != stat: continue
        total += float(entry.get("chance", entry.get("value")) or 0)
    return total


def hunter_munitions_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behavior=BEHAVIOR_ON_CRIT, stat="slash_proc")


def internal_bleeding_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behavior=BEHAVIOR_ON_IMPACT_FR, stat="slash_proc")


def internal_bleeding_threshold(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    threshold = IB_FIRE_RATE_THRESHOLD
    for entry in _entries(*sources):
        if entry.get("behavior") != BEHAVIOR_ON_IMPACT_FR: continue
        data = _behavior_data(entry)
        if "fire_rate_threshold" in data: threshold = min(threshold, float(data["fire_rate_threshold"]))
    return threshold


def encumber_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behavior=BEHAVIOR_ON_ANY_PROC, stat="random_proc")


def vigilante_flat_crit(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behavior=BEHAVIOR_ON_HIT, stat="crit_chance")


def duplicate_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behavior=BEHAVIOR_NEAR_YELLOW, stat="duplicated_hit")


def doughty_factor(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    """Scale factor for puncture×status→crit damage (value typically 1 when equipped)."""
    total = 0.0
    for entry in _entries(*sources):
        if entry.get("behavior") != BEHAVIOR_FROM_PUNCTURE_X_STATUS: continue
        total += float(entry.get("value") or 0)
    return total


def doughty_per(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    per = DOUGHTY_PER
    for entry in _entries(*sources):
        if entry.get("behavior") != BEHAVIOR_FROM_PUNCTURE_X_STATUS: continue
        data = _behavior_data(entry)
        if "per" in data: per = float(data["per"])
    return per


def doughty_crit_damage(*, puncture_weight: float, status_chance: float, factor: float, per: float = DOUGHTY_PER) -> float:
    return per * 10 * puncture_weight * status_chance * factor
