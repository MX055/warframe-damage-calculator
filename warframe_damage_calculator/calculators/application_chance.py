"""Resolve deferred application_chance / conversions entries by behaviour."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .effect_schema import (
    BEHAVIOUR_FROM_PUNCTURE_X_STATUS,
    BEHAVIOUR_NEAR_YELLOW,
    BEHAVIOUR_ON_ANY_PROC,
    BEHAVIOUR_ON_CRIT,
    BEHAVIOUR_ON_HIT,
    BEHAVIOUR_ON_IMPACT_FR,
    DOUGHTY_PER,
)
from .special_effects import iter_deferred


def _entries(*sources: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    return iter_deferred(*sources)


def sum_chance(entries: Sequence[Mapping[str, Any]], *, behaviour: str, stat: str | None = None) -> float:
    total = 0.0
    for entry in entries:
        if entry.get("behaviour") != behaviour: continue
        if stat is not None and entry.get("stat") != stat: continue
        total += float(entry.get("chance", entry.get("value")) or 0)
    return total


def hunter_munitions_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behaviour=BEHAVIOUR_ON_CRIT, stat="slash_proc")


def internal_bleeding_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behaviour=BEHAVIOUR_ON_IMPACT_FR, stat="slash_proc")


def encumber_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behaviour=BEHAVIOUR_ON_ANY_PROC, stat="random_proc")


def vigilante_flat_crit(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behaviour=BEHAVIOUR_ON_HIT, stat="crit_chance")


def duplicate_chance(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    return sum_chance(_entries(*sources), behaviour=BEHAVIOUR_NEAR_YELLOW, stat="duplicated_hit")


def doughty_factor(*sources: Sequence[Mapping[str, Any]] | None) -> float:
    """Scale factor for puncture×status→crit damage (value typically 1 when equipped)."""
    total = 0.0
    for entry in _entries(*sources):
        if entry.get("behaviour") != BEHAVIOUR_FROM_PUNCTURE_X_STATUS: continue
        total += float(entry.get("value") or 0)
    return total


def doughty_crit_damage(*, puncture_weight: float, status_chance: float, factor: float) -> float:
    return DOUGHTY_PER * 10 * puncture_weight * status_chance * factor
