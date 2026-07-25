"""First/last magazine-shot overlays and long-run shot-class mixture."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from ..fields.attack_result import AttackResult
from ..fields.calculated import AverageStats
from ..utils.types import Number
from . import formulas

MAGAZINE_POSITION_WHEN = frozenset({"first_shot", "last_shot"})
EXCLUDE_CONTINUOUS = "continuous"
EXCLUDE_INCARNON = "incarnon"

type PositionEntry = Mapping[str, Any]


def position_weights(*, magazine_capacity: Number, ammo_cost: Number, ammo_efficiency: Number) -> list[tuple[frozenset[str], float]]:
    """Long-run weights for magazine-position shot classes.

    Buffs apply while the magazine counter remains at full (first) or 1 (last).
    With ammo efficiency ``e < 1``, each ammo level is visited equally often in
    expectation, so first/last each get weight ``1/N``. At ``e >= 1`` the magazine
    never leaves full, so every shot is first-shot only. Mag size 1 makes first and
    last the same counter, so both overlays apply to every shot.
    """
    cost = max(float(ammo_cost), 0.0)
    if cost <= 0: return [(frozenset(), 1.0)]
    shots = max(float(magazine_capacity) / cost, 1.0)
    efficiency = max(float(ammo_efficiency), 0.0)
    if shots <= 1:
        return [(frozenset({"first_shot", "last_shot"}), 1.0)]
    if efficiency >= 1:
        return [(frozenset({"first_shot"}), 1.0)]
    weight = 1.0 / shots
    return [(frozenset({"first_shot"}), weight), (frozenset({"last_shot"}), weight), (frozenset(), max(0.0, 1.0 - 2.0 * weight))]


def effect_applies(entry: PositionEntry, *, delivery: str | None, form: str | None) -> bool:
    exclude = entry.get("exclude") or ()
    if EXCLUDE_CONTINUOUS in exclude and (delivery or "") == "beam": return False
    if EXCLUDE_INCARNON in exclude and (form or "normal") == "incarnon": return False
    return True


def iter_applicable(entries: Iterable[PositionEntry], *, when: frozenset[str], delivery: str | None, form: str | None) -> list[PositionEntry]:
    return [entry for entry in entries if entry.get("when") in when and effect_applies(entry, delivery=delivery, form=form)]


def _overlay_multishot(result: AttackResult, entries: Sequence[PositionEntry]) -> float:
    build, evo, base = result.build, result.evolutions, result.base
    additive = float(build.additive.multishot or 0) + float(evo.additive.multishot or 0)
    flat = 0.0
    for entry in entries:
        if entry.get("stat") != "multishot": continue
        mode = entry.get("mode", "additive")
        value = float(entry.get("value") or 0)
        if mode == "flat": flat += value
        elif mode == "additive": additive += value
    locked = bool(build.additive.multishot_lock)
    scale = 1.0 if locked else max(1.0 + additive, 0.0)
    return max(float(base.multishot if "multishot" in base else 1) * scale + flat, 1.0)


def _overlay_damage_multiplier(entries: Sequence[PositionEntry]) -> float:
    """Product across multiplicative tiers; bonuses within a tier add."""
    by_tier: dict[int, float] = {}
    for entry in entries:
        if entry.get("stat") != "damage_bonus" or entry.get("mode") != "multiplicative": continue
        tier = max(int(entry.get("tier") or 1), 1)
        by_tier[tier] = by_tier.get(tier, 0.0) + float(entry.get("value") or 0)
    factor = 1.0
    for tier in sorted(by_tier):
        factor *= max(1.0 + by_tier[tier], 1.0)
    return factor


def _class_metrics(result: AttackResult, *, entries: Sequence[PositionEntry], compute_dotph) -> dict[str, float]:
    """Hit/DoT metrics for one shot class after applying magazine-position overlays."""
    effective = result.effective
    average = result.average
    multishot = _overlay_multishot(result, entries)
    damage_multiplier = _overlay_damage_multiplier(entries)
    damage = float(effective.damage.total_damage()) * damage_multiplier
    faction = max(float(average.corpus_damage), float(average.grineer_damage), float(average.infested_damage), float(average.orokin_damage), float(average.murmur_damage), float(average.sentient_damage), 1.0)
    hit_mult = formulas.hit_multiplier(average.crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
    weakpoint_hit_mult = formulas.hit_multiplier(average.weakpoint_crit_chance, effective.crit_damage, effective.non_crit_bonus_damage, effective.non_crit_bonus_chance)
    # Temporarily patch multishot/damage scale for DoT helpers that read effective.
    saved_ms, saved_damage = effective.multishot, effective.damage
    effective.multishot = multishot
    if damage_multiplier != 1:
        effective.damage = effective.damage * damage_multiplier
    try:
        flat_dotph = float(compute_dotph(result))
        flat_weakpoint_dotph = float(compute_dotph(result, weakpoint=True))
    finally:
        effective.multishot = saved_ms
        effective.damage = saved_damage
    return {
        "flat_dph": damage * multishot * faction * hit_mult,
        "flat_weakpoint_dph": damage * multishot * float(effective.weakpoint_damage) * weakpoint_hit_mult * faction,
        "flat_dotph": flat_dotph,
        "flat_weakpoint_dotph": flat_weakpoint_dotph,
    }


def apply_magazine_position_mixture(result: AttackResult, *, compute_dotph) -> None:
    """Replace averaged hit/DoT metrics with a mixture over magazine-position shot classes."""
    entries = [*(result.build.magazine_position or ()), *(result.evolutions.magazine_position or ())]
    if not entries: return
    delivery, form = result.attack.delivery, result.attack.form or "normal"
    if not any(effect_applies(entry, delivery=delivery, form=form) for entry in entries): return

    effective = result.effective
    weights = position_weights(magazine_capacity=effective.magazine_capacity, ammo_cost=effective.ammo_cost, ammo_efficiency=effective.ammo_efficiency)
    mixed = {"flat_dph": 0.0, "flat_weakpoint_dph": 0.0, "flat_dotph": 0.0, "flat_weakpoint_dotph": 0.0}
    for when, weight in weights:
        if weight <= 0: continue
        applicable = iter_applicable(entries, when=when, delivery=delivery, form=form)
        metrics = _class_metrics(result, entries=applicable, compute_dotph=compute_dotph) if applicable else _class_metrics(result, entries=(), compute_dotph=compute_dotph)
        for key, value in metrics.items():
            mixed[key] += weight * value

    average: AverageStats = result.average
    for key, value in mixed.items():
        average[key] = value
    average.flat_dotps = average.fire_rate * average.flat_dotph
    average.flat_weakpoint_dotps = average.fire_rate * average.flat_weakpoint_dotph
    # Display: long-run expected first-shot damage multiplier (1 when unused).
    first_weight = next((weight for when, weight in weights if "first_shot" in when), 0.0)
    first_factor = _overlay_damage_multiplier(iter_applicable(entries, when=frozenset({"first_shot"}), delivery=delivery, form=form))
    average.first_shot_damage_multiplier = 1.0 + (first_factor - 1.0) * first_weight
    formulas.refresh_dps_from_dph(average)


def serialize_position_effect(*, stat: str, value: Any, mode: str, when: str, exclude: Sequence[str] = (), tier: int = 1) -> dict[str, Any]:
    entry = {"stat": stat, "value": deepcopy(value), "mode": mode, "when": when}
    if tier > 1: entry["tier"] = int(tier)
    if exclude: entry["exclude"] = list(exclude)
    return entry
