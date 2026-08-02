from __future__ import annotations

from dataclasses import replace
from ..domain.effects import ChannelValue, Scalar
from ..domain.effect_stats import STATUS_PROC_STATS
from ..domain.state import combo_multiplier_from_hits
from ..domain.status import StatusModel
from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack
from .context import CalculationContext
from .models.stats import Stats


def _values(channel: dict[str, ChannelValue], key: str) -> tuple[Scalar, ...]:
    value = channel.get(key)
    if value is None: return ()
    return tuple(value) if isinstance(value, list) else (value,)


def _value(channel: dict[str, ChannelValue], key: str, default: Scalar | None = None) -> Scalar | None:
    values = _values(channel, key)
    return values[0] if values else default


def _weapon_combo_multiplier(context: CalculationContext, stats: Stats) -> float:
    max_combo = int(context.weapon.combo.get("max_combo", 12))
    if "combo_multiplier" in context.state: return float(max(1, min(max_combo, int(context.state.combo_multiplier))))
    return float(combo_multiplier_from_hits(float(stats.get("initial_combo", 0)), max_combo))


def evaluate(effect: ResolvedEffect, *, context: CalculationContext, attack: Attack, stats: Stats, status: StatusModel, equipped: set[str]) -> ResolvedEffect | None:
    behavior = effect.automatic
    equipped_names = {name.casefold() for name in equipped}
    if any(str(name).casefold() not in equipped_names for name in _values(behavior, "equipped")): return None
    multiplier = 1.0
    source = _value(behavior, "with")
    maximum = _value(behavior, "stacks")
    stack_limit = None if maximum in (None, "inf") else int(maximum)
    if source == "unique_status_count": multiplier *= status.expected_active_types(stack_limit) * float(attack.stats.co_factor)
    elif source == "weapon_combo":
        combo = _weapon_combo_multiplier(context, stats)
        multiplier *= min(combo, stack_limit) if stack_limit is not None else combo
    elif source == "effective_multishot" and effect.family != "multishot_ammo": multiplier *= float(stats.multishot)
    elif source == "puncture_status_chance" and effect.stat != "crit_damage":
        multiplier *= min(status.proc_count_per_attack("puncture") / max(status.attempts_per_attack, 1), 1)
    elif source == "explosion_radius_lost": multiplier *= float(stats.get("explosion_radius_lost", 0))
    for condition_value in _values(behavior, "when"):
        condition = str(condition_value)
        if condition in {"normal_form", "incarnon_form"} and attack.form != condition.removesuffix("_form"): return None
        if condition == "bow_weapon" and context.weapon.subtype != "bow": return None
        if condition == "non_continuous_fire" and attack.delivery == "beam": return None
        if condition == "magazine_at_least_5" and float(context.weapon.magazine_size) < 5: return None
        if condition == "fire_rate_below_2.5" and float(stats.fire_rate) >= 2.5: return None
        if condition.endswith("_status_proc"):
            if source == "status_presence":
                if status.proc_count_per_attack(condition.removesuffix("_status_proc")) <= 0: return None
                continue
            maximum = _value(behavior, "stacks")
            limit = None if maximum in (None, "inf") else int(maximum)
            duration = float(_value(behavior, "for", status.duration))
            multiplier *= status.expected_stacks(condition.removesuffix("_status_proc"), limit, duration)
        elif condition == "critical_tier_at_least_2" and effect.stat != "crit_reset_charges":
            multiplier *= max(float(stats.crit_chance) - 1, 0)
    event = _value(behavior, "on")
    if event == "critical_hit" and effect.stat not in STATUS_PROC_STATS | {"crit_tier"}: multiplier *= min(max(float(stats.crit_chance), 0), 1)
    elif event == "near_yellow_critical_hit": multiplier *= max(1 - abs(float(stats.crit_chance) - 1), 0)
    elif event == "non_critical_hit" and effect.family != "non_critical_hit": multiplier *= max(1 - float(stats.crit_chance), 0)
    elif event == "any_status_proc" and effect.stat not in STATUS_PROC_STATS | {"random_proc"}: multiplier *= status.any_proc_probability_per_attack()
    elif event == "impact_status_proc" and effect.stat not in STATUS_PROC_STATS: multiplier *= status.per_attack_probability("impact")
    chance = _value(behavior, "chance")
    if chance is not None and effect.family != "non_critical_hit": multiplier *= float(chance)
    literal_multiplier = _value(behavior, "multiply")
    if literal_multiplier is not None: multiplier *= float(literal_multiplier)
    per = _value(behavior, "per")
    if per is not None and effect.stat not in {"crit_damage", "crit_reset_charges"}: multiplier *= float(per)
    value = effect.value * multiplier if isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool) else effect.value
    if effect.stat == "condition_overload":
        value = float(value) * status.expected_active_types() * float(attack.stats.co_factor)
        return replace(effect, stat="damage_bonus", value=value, family="unique_status")
    if effect.stat == "area_of_effect": return replace(effect, stat="explosion_radius", value=value)
    return replace(effect, value=value)
