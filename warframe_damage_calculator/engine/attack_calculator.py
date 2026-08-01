from __future__ import annotations

from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack
from .aggregation import aggregate
from .automatic import automatic_value, automatic_values
from .context import CalculationContext
from .damage import DOT_MULTIPLIERS, _base_damage, _damage, _dot_base_damage, _elemental_dot_bonuses
from .formulas import clamp, crit_multiplier, family_bonus, family_factor, hit_multiplier, refresh_metrics, true_round
from .models.attack import AttackResult, AverageAttackStats
from .models.stats import BaseAttackStats, EffectiveAttackStats, ModdedAttackStats, ResolvedStats, Stats
from .rates import HEAVY_CATEGORIES, SLAM_CATEGORIES, _melee_rate, _multishot_ammo_bonus, _ranged_rate, _stance_combo
from .secondary_enervate import average_enervate_bonus, enervate_parameters
from .spatial import is_aoe_attack, refresh_spatial, set_damage, spatial_falloff
from .stats import POSITION_EVENTS, _additive_scalar, _combined, _resolve_effects, _scalar
from .status import AFFLICTIONS_CATEGORIES, _derived_chances, _forced_procs, _special_value, _status_model, _status_vulnerability, _with_random_proc
from ..domain.status import StatusModel
from .targets import damage_multiplier, damage_total


DEFERRED_STATS = frozenset({"duplicated_hit", "random_proc", "crit_reset_charges", "crit_tier"})


def _provisional(context: CalculationContext, attack: Attack, upgrade_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...], static_upgrades: ResolvedStats | None = None, static_evolutions: ResolvedStats | None = None) -> tuple[Stats, StatusModel]:
    upgrades = static_upgrades if static_upgrades is not None else aggregate(effect for effect in upgrade_effects if not effect.automatic)
    evolutions = static_evolutions if static_evolutions is not None else aggregate(effect for effect in evolution_effects if not effect.automatic)
    total = _combined(upgrades, evolutions)
    base, original, _ = _base_damage(context, attack, evolutions)
    damage = _damage(attack, base, original, upgrades, evolutions)
    crit = _scalar(float(attack.stats.crit_chance), "crit_chance", total)
    status = _scalar(float(attack.stats.status_chance), "status_chance", total) * _status_vulnerability((*upgrade_effects, *evolution_effects))
    crit, status = _derived_chances(crit, status, total)
    ms_bonus = 0 if context.weapon.type == "melee" or total.proportional.get("multishot_lock") else float(total.proportional.get("multishot", 0))
    multishot = max(float(attack.stats.multishot) * (1 + ms_bonus), 1)
    if context.weapon.type == "melee":
        sustained, _ = _melee_rate(context, attack, total)
        instantaneous = sustained
    else:
        instantaneous, sustained, _ = _ranged_rate(context, attack, total, multishot)
    duration = _scalar(float(attack.stats.status_duration), "status_duration", total)
    stats = Stats(damage=damage, crit_chance=crit, status_chance=status, multishot=multishot, fire_rate=instantaneous, sustained_rate=sustained, status_duration=duration)
    return stats, StatusModel(damage, attack.stats.forced_procs, status, multishot, sustained, duration)


def _hit_multiplier(chance: float, tier_bonus: float, damage: float, non_crit_damage: float = 0, non_crit_chance: float = 0) -> float:
    return hit_multiplier(chance, damage, non_crit_damage, non_crit_chance) + tier_bonus * (damage - 1)


def _faction_factor(context: CalculationContext, total: ResolvedStats) -> float:
    if context.target.faction not in {"corpus", "grineer", "infested", "orokin", "murmur", "sentient"}: return 1.0
    return 1 + float(total.proportional.get(f"{context.target.faction}_damage", 0))


def _dot_value(context: CalculationContext, result: AttackResult, zone: str, *, multishot: float | None = None, damage_factor: float = 1) -> float:
    effective, average = result.effective, result.average
    damage = effective.damage * damage_factor
    if damage.total <= 0: return 0.0
    shots = float(effective.multishot if multishot is None else multishot)
    chance = average.weakpoint_crit_chance if zone == "weakpoint" else average.crit_chance
    tier_bonus = average.weakpoint_crit_tier_bonus if zone == "weakpoint" else average.crit_tier_bonus
    crit = _hit_multiplier(chance, tier_bonus, float(effective.crit_damage), float(effective.non_crit_bonus_damage), float(effective.non_crit_bonus_chance))
    faction = float(effective.faction_damage)
    weakpoint_bonus = float(effective.weakpoint_damage_bonus)
    source_effects = list(effective.special_effects)
    afflictions = bool(AFFLICTIONS_CATEGORIES & set(effective.forced_procs))
    if multishot is None and damage_factor == 1:
        proc_model = effective.status_model
    else:
        proc_model = _status_model(damage, effective.forced_procs, float(effective.status_chance), shots, average.attack_rate, float(effective.status_duration), source_effects, chance, include_random=False, afflictions=afflictions)
        if effective.status_model.random_proc_probability: proc_model = _with_random_proc(proc_model, source_effects, effective.status_model.random_proc_probability)
    value = 0.0
    dot_base = float(effective.dot_base_damage) * damage_factor
    status_damage = float(effective.status_damage)
    for kind, factor in DOT_MULTIPLIERS.items():
        target_factor = damage_multiplier(context.target, kind, zone=zone, dot=True, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects)
        if target_factor is None: continue
        proc_count = proc_model.proc_count_per_attack(kind)
        if kind == "gas" and average.attack_rate > 0 and effective.status_duration > 0:
            proc_count = min(proc_model.proc_rate(kind) * float(effective.status_duration), 10) / (average.attack_rate * float(effective.status_duration))
        critical_count = min(proc_model.critical_proc_counts.get(kind, 0), proc_count)
        critical_multiplier = max(float(effective.crit_damage), crit)
        weighted_crit = (proc_count - critical_count) * crit + critical_count * critical_multiplier
        elemental_bonus = float(effective.dot_elemental_bonuses.get(kind, 1))
        value += factor * dot_base * elemental_bonus * weighted_crit * target_factor * float(effective.status_duration) * status_damage * faction ** 2
    blast_count = proc_model.proc_count_per_attack("blast")
    if blast_count:
        blast_target = float(damage_multiplier(context.target, "blast", zone=zone, dot=True, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects) or 0)
        value += 0.3 * dot_base * blast_count * crit * blast_target * status_damage * faction ** 2
    return value * float(effective.target_vulnerability)


def _zone_damage(context: CalculationContext, result: AttackResult, zone: str, *, direct_hits: float, dot_multishot: float | None = None, damage_factor: float = 1, duplicate_multiplier: float = 1, combo_multiplier: float = 1) -> tuple[float, float] | None:
    effective, average = result.effective, result.average
    weakpoint_bonus = float(effective.weakpoint_damage_bonus)
    direct_total = damage_total(effective.damage * damage_factor, context.target, zone=zone, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects, overguard_multiplier=float(effective.overguard_damage_multiplier))
    if direct_total is None: return None
    chance = average.weakpoint_crit_chance if zone == "weakpoint" else average.crit_chance
    tier_bonus = average.weakpoint_crit_tier_bonus if zone == "weakpoint" else average.crit_tier_bonus
    faction = float(effective.faction_damage)
    direct = direct_total * direct_hits * faction * _hit_multiplier(chance, tier_bonus, float(effective.crit_damage), float(effective.non_crit_bonus_damage), float(effective.non_crit_bonus_chance)) * duplicate_multiplier * combo_multiplier * float(effective.target_vulnerability)
    cascadia = _special_value(effective.special_effects, "cascadia_empowered_proc")
    if cascadia:
        direct += sum(effective.status_model.proc_count_per_attack(kind) * cascadia * faction * float(damage_multiplier(context.target, kind, zone=zone, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects, overguard_multiplier=float(effective.overguard_damage_multiplier)) or 0) for kind in RANDOM_STATUS_TYPES | {"void"}) * float(effective.target_vulnerability)
    dot = _dot_value(context, result, zone, multishot=dot_multishot, damage_factor=damage_factor) * combo_multiplier
    return direct, dot


def _position_weights(magazine: float, ammo_cost: float, efficiency: float) -> list[tuple[frozenset[str], float]]:
    if ammo_cost <= 0: return [(frozenset(), 1)]
    shots = max(magazine / ammo_cost, 1)
    if shots <= 1: return [(frozenset(POSITION_EVENTS), 1)]
    if efficiency >= 1: return [(frozenset({"magazine_first_shot"}), 1)]
    weight = 1 / shots
    return [(frozenset({"magazine_first_shot"}), weight), (frozenset({"magazine_last_shot"}), weight), (frozenset(), max(0, 1 - 2 * weight))]


def _apply_position_mixture(context: CalculationContext, result: AttackResult, effects: list[ResolvedEffect]) -> None:
    if context.weapon.type == "melee": return
    if not effects: return
    effective, average, spatial = result.effective, result.average, result.spatial
    mixed_direct = 0.0
    mixed_dot = 0.0
    weights = _position_weights(float(effective.magazine_capacity), float(effective.ammo_cost), float(effective.ammo_efficiency))
    for events, weight in weights:
        active = [effect for effect in effects if automatic_value(effect, "on") in events]
        family_bonuses: dict[str, float] = {}
        multishot_bonus = 0.0
        for effect in active:
            if effect.stat == "damage_bonus": family_bonuses[effect.family] = family_bonuses.get(effect.family, 0) + float(effect.value)
            elif effect.stat == "multishot": multishot_bonus += float(effect.value)
        damage_factor = 1.0
        for value in family_bonuses.values(): damage_factor *= max(1 + value, 1)
        multishot = max(float(effective.multishot) + multishot_bonus, 1)
        zone = next(iter(context.target.bodyparts.values())).type
        damage = _zone_damage(context, result, zone, direct_hits=multishot, dot_multishot=multishot, damage_factor=damage_factor)
        if damage is None: continue
        direct, dot = damage
        mixed_direct += direct * weight
        mixed_dot += dot * weight
    set_damage(average, spatial, mixed_direct, mixed_dot)
    first = [effect for effect in effects if automatic_value(effect, "on") == "magazine_first_shot" and effect.stat == "damage_bonus"]
    first_factor = 1.0
    for family in {effect.family for effect in first}: first_factor *= 1 + sum(float(effect.value) for effect in first if effect.family == family)
    first_weight = next((weight for events, weight in weights if "magazine_first_shot" in events), 0)
    average.first_shot_damage_multiplier = 1 + (first_factor - 1) * first_weight
    refresh_metrics(average)
    refresh_spatial(spatial, average.attack_rate)


def _calculate_attack(context: CalculationContext, attack: Attack, upgrade_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...], *, static_upgrades: ResolvedStats | None = None, static_evolutions: ResolvedStats | None = None, automatic_model_override: StatusModel | None = None, status_effects_override: dict[str, float] | None = None, random_proc_probability: float = 0) -> AttackResult:
    provisional, provisional_model = _provisional(context, attack, upgrade_effects, evolution_effects, static_upgrades, static_evolutions)
    equipped = {upgrade.name for upgrade in context.loadout.ranked_upgrades}
    initial_upgrade_effects, _ = _resolve_effects(context, attack, upgrade_effects, provisional, provisional_model, equipped)
    initial_evolution_effects, _ = _resolve_effects(context, attack, evolution_effects, provisional, provisional_model, equipped)
    stable = lambda effect: not any(str(value).endswith("_status_proc") for value in automatic_values(effect, "when"))
    initial_upgrades = aggregate(effect for effect in initial_upgrade_effects if stable(effect) and effect.stat not in DEFERRED_STATS)
    initial_evolutions = aggregate(effect for effect in initial_evolution_effects if stable(effect) and effect.stat not in DEFERRED_STATS)
    initial_total = _combined(initial_upgrades, initial_evolutions)
    initial_heavy = context.weapon.type == "melee" and attack.category in HEAVY_CATEGORIES
    initial_upgrade_crit = float(initial_upgrades.proportional.get("crit_chance", 0)) * (2 if initial_heavy else 1)
    initial_crit = max((float(attack.stats.crit_chance) + float(initial_total.base.get("crit_chance", 0))) * (1 + initial_upgrade_crit + float(initial_evolutions.proportional.get("crit_chance", 0))) * family_factor(initial_total, "crit_chance") + float(initial_total.flat.get("crit_chance", 0)), 0)
    initial_status = _scalar(float(attack.stats.status_chance), "status_chance", initial_total) * _status_vulnerability((*initial_upgrade_effects, *initial_evolution_effects))
    initial_crit, initial_status = _derived_chances(initial_crit, initial_status, initial_total)
    initial_ms_bonus = 0 if context.weapon.type == "melee" or initial_total.proportional.get("multishot_lock") else float(initial_total.proportional.get("multishot", 0))
    initial_multishot = max(float(attack.stats.multishot) * (1 + initial_ms_bonus), 1)
    acquisition = [effect for effect in (*initial_upgrade_effects, *initial_evolution_effects) if effect.stat == "duplicated_hit"]
    duplicate_acquisition = _special_value(acquisition, "duplicated_hit")
    if context.weapon.type == "melee":
        acquisition_attempts = initial_multishot + duplicate_acquisition * max(0, 1 - abs(initial_crit - 1))
        initial_rate, _ = _melee_rate(context, attack, initial_total)
    else:
        acquisition_attempts = initial_multishot
        _, initial_rate, _ = _ranged_rate(context, attack, initial_total, initial_multishot)
    initial_duration = _scalar(float(attack.stats.status_duration), "status_duration", initial_total)
    initial_effects = (*initial_upgrade_effects, *initial_evolution_effects)
    initial_forced = _forced_procs(attack, initial_effects)
    automatic_model = _status_model(provisional_model.damage, initial_forced, initial_status, acquisition_attempts, initial_rate, initial_duration, initial_effects, initial_crit, afflictions=bool(AFFLICTIONS_CATEGORIES & set(initial_forced)))
    if automatic_model_override is not None: automatic_model = automatic_model_override
    upgrades_resolved, upgrade_positions = _resolve_effects(context, attack, upgrade_effects, provisional, automatic_model, equipped)
    evolution_resolved, evolution_positions = _resolve_effects(context, attack, evolution_effects, provisional, automatic_model, equipped)
    upgrades = aggregate(effect for effect in upgrades_resolved if automatic_value(effect, "on") not in POSITION_EVENTS and effect.stat not in DEFERRED_STATS and not (effect.stat == "crit_damage" and automatic_value(effect, "with") == "puncture_status_chance"))
    evolutions = aggregate(effect for effect in evolution_resolved if automatic_value(effect, "on") not in POSITION_EVENTS and effect.stat not in DEFERRED_STATS)
    modded_upgrades = aggregate(effect for effect in upgrades_resolved if not effect.automatic and automatic_value(effect, "on") not in POSITION_EVENTS and effect.stat not in DEFERRED_STATS and not (effect.stat == "crit_damage" and automatic_value(effect, "with") == "puncture_status_chance"))
    modded_evolutions = aggregate(effect for effect in evolution_resolved if not effect.automatic and automatic_value(effect, "on") not in POSITION_EVENTS and effect.stat not in DEFERRED_STATS)
    total = _combined(upgrades, evolutions)
    modded_total = _combined(modded_upgrades, modded_evolutions)
    base_damage, original, displayed_base_damage = _base_damage(context, attack, evolutions)
    modded_base_damage, modded_original, _ = _base_damage(context, attack, modded_evolutions)
    progenitor = context.loadout.progenitor if "progenitor" in context.weapon.traits else None
    modded_damage = _damage(attack, modded_base_damage, modded_original, modded_upgrades, modded_evolutions, progenitor)
    damage = _damage(attack, base_damage, original, upgrades, evolutions, progenitor)
    heavy = context.weapon.type == "melee" and attack.category in HEAVY_CATEGORIES
    modded_upgrade_crit = float(modded_upgrades.proportional.get("crit_chance", 0)) * (2 if heavy else 1)
    modded_crit_base = float(attack.stats.crit_chance) + float(modded_total.base.get("crit_chance", 0))
    modded_crit = max(modded_crit_base * (1 + modded_upgrade_crit + float(modded_evolutions.proportional.get("crit_chance", 0))) * family_factor(modded_total, "crit_chance") + float(modded_total.flat.get("crit_chance", 0)), 0)
    upgrade_crit = float(upgrades.proportional.get("crit_chance", 0)) * (2 if heavy else 1)
    crit_base = float(attack.stats.crit_chance) + float(total.base.get("crit_chance", 0))
    crit = max(crit_base * (1 + upgrade_crit + float(evolutions.proportional.get("crit_chance", 0))) * family_factor(total, "crit_chance") + float(total.flat.get("crit_chance", 0)), 0)
    resolved_effects = (*upgrades_resolved, *evolution_resolved)
    modded_status = _scalar(float(attack.stats.status_chance), "status_chance", modded_total)
    modded_crit, modded_status = _derived_chances(modded_crit, modded_status, modded_total)
    status = _scalar(float(attack.stats.status_chance), "status_chance", total) * _status_vulnerability(resolved_effects)
    crit, status = _derived_chances(crit, status, total)
    if context.weapon.type == "melee" and attack.category == "slide":
        modded_crit *= max(1 + float(modded_total.proportional.get("slide_crit_chance", 0)), 0)
        crit *= max(1 + float(total.proportional.get("slide_crit_chance", 0)), 0)
    modded_crit_damage = _scalar(float(attack.stats.crit_damage), "crit_damage", modded_total, minimum=1)
    crit_damage = _scalar(float(attack.stats.crit_damage), "crit_damage", total, minimum=1)
    doughty = next((effect for effect in (*upgrades_resolved, *evolution_resolved) if effect.stat == "crit_damage" and automatic_value(effect, "with") == "puncture_status_chance"), None)
    doughty_bonus = 0.0
    weakpoint_common = float(total.proportional.get("weakpoint_crit_chance", 0))
    weakpoint_family = sum(float(family.get("weakpoint_crit_chance", 0)) for family in total.families.values())
    weakpoint_crit = 0.0 if context.weapon.type == "melee" else max(crit + float(attack.stats.crit_chance) * (weakpoint_common + weakpoint_family) + float(total.flat.get("weakpoint_crit_chance", 0)), 0)
    crit_tier_chance = clamp(_special_value((*upgrades_resolved, *evolution_resolved), "crit_tier", "critical_hit"), 0, 1)
    modded_ms_bonus = 0 if context.weapon.type == "melee" or modded_total.proportional.get("multishot_lock") else float(modded_total.proportional.get("multishot", 0))
    modded_multishot = max(float(attack.stats.multishot) * (1 + modded_ms_bonus), 1)
    ms_bonus = 0 if context.weapon.type == "melee" or total.proportional.get("multishot_lock") else float(total.proportional.get("multishot", 0))
    ms_ammo_bonus = _multishot_ammo_bonus(total)
    if attack.delivery == "beam" and ms_ammo_bonus and not total.proportional.get("multishot_lock"): ms_bonus *= 1 + ms_ammo_bonus
    multishot = max(float(attack.stats.multishot) * (1 + ms_bonus), 1)
    if attack.delivery != "beam" and ms_ammo_bonus: damage *= 1 + ms_ammo_bonus * (1 - 1 / multishot)
    if context.weapon.type == "melee":
        _, base_category_stats = _melee_rate(context, attack, ResolvedStats(), include_stance=False)
        modded_instant_rate, modded_category_stats = _melee_rate(context, attack, modded_total, include_stance=False)
        instant_rate, category_stats = _melee_rate(context, attack, total)
        fire_rate = instant_rate
        stance = _stance_combo(context, attack)
        if stance: damage *= max(float(stance.get("multiplier", 1)), 0)
        if attack.category in SLAM_CATEGORIES: damage *= max(1 + float(total.proportional.get("slam_damage", 0)), 0)
    else:
        _, _, base_category_stats = _ranged_rate(context, attack, ResolvedStats(), float(attack.stats.multishot))
        modded_instant_rate, _, modded_category_stats = _ranged_rate(context, attack, modded_total, modded_multishot)
        instant_rate, fire_rate, category_stats = _ranged_rate(context, attack, total, multishot)
    duration = _scalar(float(attack.stats.status_duration), "status_duration", total)
    forced = _forced_procs(attack, (*upgrades_resolved, *evolution_resolved))
    duplicate = clamp(_special_value((*upgrades_resolved, *evolution_resolved), "duplicated_hit"), 0, 1)
    duplicate_multiplier = 1 + duplicate * max(0, 1 - abs(crit - 1)) if context.weapon.type == "melee" else 1
    status_attempts = multishot + duplicate * max(0, 1 - abs(crit - 1)) if context.weapon.type == "melee" else multishot
    afflictions = bool(AFFLICTIONS_CATEGORIES & set(forced))
    if automatic_model_override is not None:
        afflictions = afflictions or any(automatic_model_override.proc_count_per_attack(kind) > 0 for kind in AFFLICTIONS_CATEGORIES)
    status_model = _status_model(damage, forced, status, status_attempts, fire_rate, duration, resolved_effects, crit, include_random=False, afflictions=afflictions)
    puncture_stacks = status_model.non_damage_effects()["puncture"] if status_effects_override is None else status_effects_override.get("puncture", 0)
    puncture_bonus = 0 if is_aoe_attack(attack) else 0.05 * puncture_stacks
    if puncture_bonus:
        crit += puncture_bonus
        weakpoint_crit += puncture_bonus
        status_model = _status_model(damage, forced, status, status_attempts, fire_rate, duration, resolved_effects, crit, include_random=False, afflictions=afflictions)
    if random_proc_probability: status_model = _with_random_proc(status_model, resolved_effects, random_proc_probability)
    if doughty is not None:
        per = float(automatic_value(doughty, "per", 0.1) or 0.1)
        maximum = 50 if doughty.maximum is None else float(doughty.maximum)
        puncture_source = status_model if automatic_model_override is None else automatic_model_override
        puncture_chance = min(puncture_source.proc_count_per_attack("puncture") / max(status_attempts, 1), 1)
        doughty_bonus = true_round(min(puncture_chance / per * float(doughty.value), maximum), 1)
        crit_damage += doughty_bonus
    status_effects = dict(status_model.non_damage_effects() if status_effects_override is None else status_effects_override)
    status_effects["armor_reduction"] = min(status_effects.get("puncture", 0) * _special_value(resolved_effects, "armor_reduction"), 1)
    cold_stacks = status_effects["cold"]
    crit_damage += 1.0 if cold_stacks >= 10 else min(0.1 * min(cold_stacks, 1) + 0.05 * max(cold_stacks - 1, 0), 0.5)
    faction = _faction_factor(context, total)
    non_crit_damage = family_bonus(total, "non_critical_hit", "damage_bonus") + float(total.proportional.get("non_crit_bonus_damage", 0))
    non_crit_chance = max((float(automatic_value(effect, "chance", 0) or 0) for effect in (*upgrades_resolved, *evolution_resolved) if effect.family == "non_critical_hit"), default=0)
    weakpoint_bonus = max(float(total.proportional.get("weakpoint_damage", 0)) + float(total.proportional.get("sharpshot_bonus", 0)), 0)
    overguard_effect = float(total.proportional.get("overguard_damage_multiplier", 0))
    effective = EffectiveAttackStats(damage=damage, dot_base_damage=_dot_base_damage(attack, base_damage, original, upgrades, evolutions), dot_elemental_bonuses=_elemental_dot_bonuses(total, progenitor), forced_procs=forced, status_model=status_model, crit_chance=crit, weakpoint_crit_chance=weakpoint_crit, crit_damage=crit_damage, status_chance=status, status_duration=duration, status_damage=max(1 + float(total.proportional.get("status_damage", 0)), 1), multishot=multishot, fire_rate=instant_rate, attack_event_rate=fire_rate, faction_damage=faction, target_vulnerability=max(1 + float(total.proportional.get("unique_enemy_vulnerability_multiplier", 0)), 0), overguard_damage_multiplier=overguard_effect if overguard_effect else 1, non_crit_bonus_damage=non_crit_damage, non_crit_bonus_chance=non_crit_chance, weakpoint_damage_bonus=weakpoint_bonus, special_effects=tuple(resolved_effects), **category_stats)
    for stat in ("range", "punch_through", "accuracy", "recoil", "zoom", "ammo_maximum"):
        base_value = float(getattr(attack.stats, stat, 0)) if hasattr(attack.stats, stat) else 0
        effective[stat] = _additive_scalar(base_value, stat, total) if stat == "punch_through" else _scalar(base_value, stat, total)
    projectile_speed = max(1 + float(total.proportional.get("projectile_speed", 0)), 0)
    effective.projectile_speed = projectile_speed
    radius_bonus = float(total.proportional.get("explosion_radius", 0)) + (float(total.proportional.get("slam_radius", 0)) if attack.category in SLAM_CATEGORIES else 0)
    range_scale = max(1 + radius_bonus, 0) if is_aoe_attack(attack) else projectile_speed
    effective.start_range = float(attack.stats.falloff.get("start_range", 0)) * range_scale
    effective.end_range = float(attack.stats.falloff.get("end_range", 0)) * range_scale
    maximum = attack.stats.max_range
    if maximum is None and "end_range" in attack.stats.falloff: maximum = float(attack.stats.falloff["end_range"])
    effective.max_range = None if maximum is None else float(maximum) * range_scale
    final_multiplier = attack.stats.falloff.get("final_multiplier")
    effective.final_multiplier = 1.0 if final_multiplier is None else float(final_multiplier)
    effective.noise_level = total.proportional.get("noise_level", attack.stats.noise_level)
    base = BaseAttackStats(damage=displayed_base_damage, forced_procs=attack.stats.forced_procs, crit_chance=attack.stats.crit_chance, crit_damage=attack.stats.crit_damage, status_chance=attack.stats.status_chance, status_duration=attack.stats.status_duration, multishot=attack.stats.multishot, fire_rate=attack.stats.fire_rate, **base_category_stats)
    modded_duration = _scalar(float(attack.stats.status_duration), "status_duration", modded_total)
    modded = ModdedAttackStats(damage=modded_damage, crit_chance=modded_crit, crit_damage=modded_crit_damage, status_chance=modded_status, status_duration=modded_duration, multishot=modded_multishot, fire_rate=modded_instant_rate, **modded_category_stats)
    body_crit, weak_crit = crit, weakpoint_crit
    if context.weapon.type == "secondary":
        per_stack, reset = enervate_parameters([*upgrades_resolved, *evolution_resolved])
        body_bonus = average_enervate_bonus(crit, per_stack, reset)
        weak_bonus = average_enervate_bonus(weakpoint_crit, per_stack, reset)
        body_crit += body_bonus
        weak_crit += weak_bonus
    else:
        body_bonus = weak_bonus = 0
    body_tier_bonus = min(body_crit, 1) * crit_tier_chance
    weak_tier_bonus = min(weak_crit, 1) * crit_tier_chance
    falloff_multiplier, spatial = spatial_falloff(attack, effective)
    average = AverageAttackStats(damage=damage, crit_chance=body_crit, crit_damage=crit_damage, status_chance=status, status_duration=duration, multishot=multishot, fire_rate=instant_rate, magazine_capacity=float(category_stats.get("magazine_capacity", 0)), reload_time=float(category_stats.get("reload_time", 0)), ammo_cost=float(category_stats.get("ammo_cost", 0)), ammo_efficiency=float(category_stats.get("ammo_efficiency", 0)), punch_through=float(effective.get("punch_through", 0)), burst_count=float(category_stats.get("burst_count", 1)), burst_delay=float(category_stats.get("burst_delay", 0)), charge_time=float(category_stats.get("charge_time", 0)), attack_speed=float(category_stats.get("attack_speed", instant_rate if context.weapon.type == "melee" else 0)), heavy_attack_speed=float(category_stats.get("heavy_attack_speed", 1)), heavy_attack_efficiency=float(category_stats.get("heavy_attack_efficiency", 0)), initial_combo=float(category_stats.get("initial_combo", 0)), crit_multiplier=crit_multiplier(body_crit + body_tier_bonus, crit_damage), weakpoint_crit_chance=weak_crit, weakpoint_crit_multiplier=crit_multiplier(weak_crit + weak_tier_bonus, crit_damage), attack_rate=fire_rate, procs_per_shot=status_model.expected_procs_per_attack, melee_duplicate_multiplier=duplicate_multiplier, melee_doughty_bonus=doughty_bonus, crit_tier_bonus=body_tier_bonus, weakpoint_crit_tier_bonus=weak_tier_bonus, secondary_enervate_bonus=body_bonus, weakpoint_secondary_enervate_bonus=weak_bonus, falloff_multiplier=falloff_multiplier)
    result = AttackResult(attack, base, modded, effective, upgrades, evolutions, average, spatial, status_effects)
    combo_multiplier = 1
    if heavy:
        combo_multiplier = max(1, min(int(context.weapon.combo.get("max_combo", 12)), int(context.state.combo)))
    average.combo_multiplier = combo_multiplier
    zone = next(iter(context.target.bodyparts.values())).type
    zone_damage = _zone_damage(context, result, zone, direct_hits=1 if context.weapon.type == "melee" else multishot, duplicate_multiplier=duplicate_multiplier, combo_multiplier=combo_multiplier)
    if zone_damage is not None:
        direct, dot = zone_damage
        set_damage(average, spatial, direct, dot)
    refresh_metrics(average)
    refresh_spatial(spatial, average.attack_rate)
    _apply_position_mixture(context, result, [*upgrade_positions, *evolution_positions])
    return result


class AttackCalculator:
    __slots__ = ("context", "upgrade_effects", "evolution_effects", "static_upgrades", "static_evolutions")

    def __init__(self, context: CalculationContext, upgrade_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...]) -> None:
        self.context = context
        self.upgrade_effects = upgrade_effects
        self.evolution_effects = evolution_effects
        self.static_upgrades = aggregate(effect for effect in upgrade_effects if not effect.automatic)
        self.static_evolutions = aggregate(effect for effect in evolution_effects if not effect.automatic)

    def calculate(self, attack: Attack, *, automatic_model: StatusModel | None = None, status_effects: dict[str, float] | None = None, random_proc_probability: float = 0) -> AttackResult:
        return _calculate_attack(self.context, attack, self.upgrade_effects, self.evolution_effects, static_upgrades=self.static_upgrades, static_evolutions=self.static_evolutions, automatic_model_override=automatic_model, status_effects_override=status_effects, random_proc_probability=random_proc_probability)
