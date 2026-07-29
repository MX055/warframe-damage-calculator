from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..domain.damage import Dist
from ..domain.results import ResolvedStats, Stats
from ..domain.upgrades import ResolvedEffect


DAMAGE_TYPES = frozenset({"impact", "puncture", "slash", "heat", "cold", "electricity", "toxin", "blast", "radiation", "gas", "magnetic", "viral", "corrosive", "void", "tau", "true"})


def _merge(target: Stats, stat: str, value: Any) -> None:
    if stat in DAMAGE_TYPES:
        damage = target.get("damage", Dist())
        target["damage"] = damage + Dist({stat: float(value)})
    elif stat in {"damage", "forced_procs"} and isinstance(value, Mapping):
        target[stat] = target.get(stat, Dist()) + Dist(value)
    elif stat == "status_effect_stacks":
        target[stat] = [*target.get(stat, []), value]
    elif isinstance(value, bool):
        target[stat] = bool(target.get(stat, False)) or value
    elif isinstance(value, (int, float)):
        target[stat] = float(target.get(stat, 0)) + value
    elif isinstance(value, Mapping):
        current = target.get(stat, {})
        target[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in dict(current) | dict(value)}
    elif stat == "noise_level":
        target[stat] = "silent" if "silent" in {target.get(stat), value} else value
    else:
        target[stat] = value


def aggregate(effects: Iterable[ResolvedEffect]) -> ResolvedStats:
    result = ResolvedStats()
    for effect in effects:
        if effect.family != "common" and effect.mode == "proportional":
            target = result.families.setdefault(effect.family, Stats())
        else:
            target = getattr(result, effect.mode)
        _merge(target, effect.stat, effect.value)
        if effect.maximum is not None: result.maximums[effect.stat] = min(result.maximums.get(effect.stat, effect.maximum), effect.maximum)
    return result


def merge(target: ResolvedStats, source: ResolvedStats) -> None:
    for mode in ("proportional", "base", "flat"):
        for stat, value in getattr(source, mode).items(): _merge(getattr(target, mode), stat, value)
    for family, stats in source.families.items():
        destination = target.families.setdefault(family, Stats())
        for stat, value in stats.items(): _merge(destination, stat, value)
    for stat, maximum in source.maximums.items(): target.maximums[stat] = min(target.maximums.get(stat, maximum), maximum)
