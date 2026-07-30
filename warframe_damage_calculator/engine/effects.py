from __future__ import annotations

from dataclasses import replace
from ..domain.effects import ChannelValue, Scalar
from ..domain.results import Stats
from ..domain.status import STATUS_TYPES, StatusModel
from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack
from .context import CalculationContext


STATUS_PROC_STATS = frozenset(f"{kind}_proc" for kind in STATUS_TYPES)
HANDLED_EFFECT_STATS = frozenset({
    "accuracy", "afflictions_proc_multiplier", "ammo_efficiency", "ammo_maximum", "area_of_effect", "armor_reduction", "attack_speed", "bleed_on_impact",
    "cold", "condition_overload", "corpus_damage", "corrosive", "crit_chance", "crit_damage", "crit_from_status",
    "crit_reset_charges", "crit_tier", "damage", "damage_bonus", "debilitate_proc_chance", "duplicated_hit", "electricity", "explosion_radius",
    "fire_rate", "fire_rate_lock", "gas", "grineer_damage", "heat", "heavy_attack_efficiency", "heavy_attack_speed", "impact",
    "impact_to_puncture_conversion", "infested_damage", "initial_combo", "magazine_capacity", "magnetic", "multishot", "multishot_lock",
    "murmur_damage", "noise_level", "orokin_damage", "overguard_damage_multiplier", "projectile_speed", "puncture", "puncture_proc",
    "punch_through", "radiation", "random_proc", "range", "recoil", "reload_speed", "sentient_damage", "sharpshot_bonus", "slam_damage",
    "slam_radius", "slash", "slash_proc", "status_chance", "status_damage", "status_duration", "status_from_crit", "status_vulnerability",
    "toxin", "unique_enemy_vulnerability_multiplier", "viral", "weakpoint_crit_chance", "weakpoint_damage", "zoom",
})
NON_CALCULATION_EFFECT_STATS = frozenset({
    "aerial_melee_attack_range", "ammo_efficiency_chance", "ammo_replenish_chance", "ammo_restore", "body_shot_crit_chance_multiplier",
    "bullet_jump", "combo_count", "combo_duration", "combo_gain_chance", "combo_on_ammo_pickup", "combo_on_finisher", "combo_timer_pause",
    "damage_field_duration", "double_jump_strength", "extra_jump", "finisher_damage", "follow_through", "health_regen", "holstered_reload",
    "incarnon_charge_rate", "instant_reload_chance", "magazine_restore_chance", "movement_speed", "movement_speed_while_aiming", "overshield",
    "parkour_velocity", "parry_angle", "slide", "slide_attack_range", "sprint_speed", "stun_on_finisher",
})


def automatic_values(source: ResolvedEffect | dict[str, ChannelValue], key: str) -> tuple[Scalar, ...]:
    channel = source.automatic if isinstance(source, ResolvedEffect) else source
    value = channel.get(key)
    if value is None: return ()
    return tuple(value) if isinstance(value, list) else (value,)


def automatic_value(source: ResolvedEffect | dict[str, ChannelValue], key: str, default: Scalar | None = None) -> Scalar | None:
    values = automatic_values(source, key)
    return values[0] if values else default


def evaluate(effect: ResolvedEffect, *, context: CalculationContext, attack: Attack, stats: Stats, status: StatusModel, equipped: set[str]) -> ResolvedEffect | None:
    behavior = effect.automatic
    equipped_names = {name.casefold() for name in equipped}
    if any(str(name).casefold() not in equipped_names for name in automatic_values(behavior, "equipped")): return None
    multiplier = 1.0
    source = automatic_value(behavior, "with")
    maximum = automatic_value(behavior, "stacks")
    stack_limit = None if maximum in (None, "inf") else int(maximum)
    if source == "unique_status_count": multiplier *= status.expected_active_types(stack_limit) * float(attack.stats.co_factor)
    elif source == "weapon_combo": multiplier *= min(float(context.state.combo), stack_limit) if stack_limit is not None else float(context.state.combo)
    elif source == "effective_multishot" and effect.family != "multishot_ammo": multiplier *= float(stats.multishot)
    elif source == "puncture_status_chance" and effect.stat != "crit_damage":
        multiplier *= min(status.proc_count_per_attack("puncture") / max(status.attempts_per_attack, 1), 1)
    for condition_value in automatic_values(behavior, "when"):
        condition = str(condition_value)
        if condition in {"normal_form", "incarnon_form"} and attack.form != condition.removesuffix("_form"): return None
        if condition == "bow_weapon" and context.weapon.subtype != "bow": return None
        if condition == "non_continuous_fire" and attack.delivery == "beam": return None
        if condition == "magazine_at_least_5" and float(context.weapon.magazine_size) < 5: return None
        if condition == "fire_rate_below_2.5" and float(stats.fire_rate) >= 2.5: return None
        if condition.endswith("_status_proc"):
            maximum = automatic_value(behavior, "stacks")
            limit = None if maximum in (None, "inf") else int(maximum)
            duration = float(automatic_value(behavior, "for", status.duration))
            multiplier *= status.expected_stacks(condition.removesuffix("_status_proc"), limit, duration)
        elif condition == "critical_tier_at_least_2" and effect.stat != "crit_reset_charges":
            multiplier *= max(float(stats.crit_chance) - 1, 0)
    event = automatic_value(behavior, "on")
    if event == "critical_hit" and effect.stat not in STATUS_PROC_STATS | {"crit_tier"}: multiplier *= min(max(float(stats.crit_chance), 0), 1)
    elif event == "near_yellow_critical_hit" and effect.stat != "duplicated_hit": multiplier *= max(1 - abs(float(stats.crit_chance) - 1), 0)
    elif event == "non_critical_hit" and effect.family != "non_critical_hit": multiplier *= max(1 - float(stats.crit_chance), 0)
    elif event == "any_status_proc" and effect.stat not in STATUS_PROC_STATS | {"random_proc"}: multiplier *= status.any_proc_probability_per_attack()
    elif event == "impact_status_proc" and effect.stat not in STATUS_PROC_STATS: multiplier *= status.per_attack_probability("impact")
    chance = automatic_value(behavior, "chance")
    if chance is not None and effect.family != "non_critical_hit": multiplier *= float(chance)
    literal_multiplier = automatic_value(behavior, "multiply")
    if literal_multiplier is not None: multiplier *= float(literal_multiplier)
    per = automatic_value(behavior, "per")
    if per is not None and effect.stat not in {"crit_damage", "crit_reset_charges"}: multiplier *= float(per)
    value = effect.value * multiplier if isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool) else effect.value
    if effect.stat == "condition_overload":
        value = float(value) * status.expected_active_types() * float(attack.stats.co_factor)
        return replace(effect, stat="damage_bonus", value=value, family="unique_status")
    if effect.stat == "area_of_effect": return replace(effect, stat="explosion_radius", value=value)
    return replace(effect, value=value)
