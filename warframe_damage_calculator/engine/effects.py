from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..domain.effects import ChannelValue, Scalar
from ..domain.results import Stats
from ..domain.upgrades import ResolvedEffect
from .status import StatusModel


def _values(channel: dict[str, ChannelValue], key: str) -> tuple[Scalar, ...]:
    value = channel.get(key)
    if value is None: return ()
    return tuple(value) if isinstance(value, list) else (value,)


def _value(channel: dict[str, ChannelValue], key: str, default: Scalar | None = None) -> Scalar | None:
    values = _values(channel, key)
    return values[0] if values else default


def evaluate(effect: ResolvedEffect, *, weapon: Any, attack: Any, stats: Stats, status: StatusModel, equipped: set[str]) -> ResolvedEffect | None:
    behavior = effect.automatic
    equipped_names = {name.casefold() for name in equipped}
    if any(str(name).casefold() not in equipped_names for name in _values(behavior, "equipped")): return None
    multiplier = 1.0
    source = _value(behavior, "with")
    maximum = _value(behavior, "stacks")
    stack_limit = None if maximum in (None, "inf") else int(maximum)
    if source == "unique_status_count": multiplier *= status.expected_unique(stack_limit) * float(attack.stats.co_factor)
    elif source == "weapon_combo": multiplier *= min(float(weapon.runtime.combo), stack_limit) if stack_limit is not None else float(weapon.runtime.combo)
    elif source == "effective_multishot" and effect.family != "multishot_ammo": multiplier *= float(stats.multishot)
    elif source == "puncture_status_chance" and effect.stat != "crit_damage": multiplier *= status.status_chance * status.damage.weight("puncture")
    for condition_value in _values(behavior, "when"):
        condition = str(condition_value)
        if condition in {"normal_form", "incarnon_form"} and attack.form != condition.removesuffix("_form"): return None
        if condition == "bow_weapon" and weapon.subtype != "bow": return None
        if condition == "non_continuous_fire" and attack.delivery == "beam": return None
        if condition == "magazine_at_least_5" and float(weapon.magazine_size) < 5: return None
        if condition == "fire_rate_below_2.5" and float(stats.fire_rate) >= 2.5: return None
        if condition.endswith("_status_proc"):
            maximum = _value(behavior, "stacks")
            limit = None if maximum in (None, "inf") else int(maximum)
            duration = float(_value(behavior, "for", status.duration))
            multiplier *= status.expected_stacks(condition.removesuffix("_status_proc"), limit, duration)
        elif condition == "critical_tier_at_least_2" and effect.stat != "crit_reset_charges":
            multiplier *= max(float(stats.crit_chance) - 1, 0)
    event = _value(behavior, "on")
    if event == "critical_hit" and effect.stat not in {"slash_proc", "crit_tier"}: multiplier *= min(max(float(stats.crit_chance), 0), 1)
    elif event == "near_yellow_critical_hit" and effect.stat != "duplicated_hit": multiplier *= max(1 - abs(float(stats.crit_chance) - 1), 0)
    elif event == "non_critical_hit" and effect.family != "non_critical_hit": multiplier *= max(1 - float(stats.crit_chance), 0)
    elif event == "any_status_proc" and effect.stat != "random_proc": multiplier *= min(status.status_chance * status.attempts_per_attack, 1)
    elif event == "impact_status_proc" and effect.stat != "slash_proc": multiplier *= min(status.status_chance * status.attempts_per_attack * status.damage.weight("impact"), 1)
    chance = _value(behavior, "chance")
    if chance is not None and effect.family != "non_critical_hit": multiplier *= float(chance)
    literal_multiplier = _value(behavior, "multiply")
    if literal_multiplier is not None: multiplier *= float(literal_multiplier)
    per = _value(behavior, "per")
    if per is not None and effect.stat not in {"crit_damage", "crit_reset_charges"}: multiplier *= float(per)
    value = effect.value * multiplier if isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool) else effect.value
    return replace(effect, value=value)
