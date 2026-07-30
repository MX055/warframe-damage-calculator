from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..domain.damage import Dist
from ..domain.results import AttackResult, AverageAttackStats, BaseAttackStats, EffectiveAttackStats, ModdedAttackStats, ResolvedStats, SpatialMetrics, Stats
from ..domain.upgrades import ResolvedEffect, Upgrade
from ..domain.weapons import Attack
from .aggregation import DAMAGE_TYPES, aggregate, merge
from .context import CalculationContext
from .effects import automatic_value, automatic_values, evaluate
from .formulas import DOT_MULTIPLIERS, aoe_damage_mass, average_falloff_multiplier, clamp, crit_multiplier, family_bonus, family_factor, hit_multiplier, ranged_falloff_multiplier, refresh_metrics, true_round
from .special import average_enervate_bonus, enervate_parameters
from ..domain.status import COMBINED_STATUS_COMPONENTS, RANDOM_STATUS_TYPES, STATUS_TYPES, StatusModel, attack_proc_chance
from .targets import ZONE_FIELDS, damage_multiplier, damage_total


HEAVY_CATEGORIES = frozenset({"heavy", "heavy_slam"})
SLAM_CATEGORIES = frozenset({"slam", "heavy_slam"})
AFFLICTIONS_CATEGORIES = frozenset({"lifted", "knockdown", "ragdoll"})
POSITION_EVENTS = frozenset({"magazine_first_shot", "magazine_last_shot"})
DEFERRED_STATS = frozenset({"duplicated_hit", "random_proc", "crit_reset_charges", "crit_tier"})
DEFERRED_FAMILIES = frozenset({"magazine_first_shot", "magazine_last_shot"})
PROC_STATS = frozenset(f"{damage_type}_proc" for damage_type in STATUS_TYPES)
def _scalar(base: float, stat: str, modifiers: ResolvedStats, *, minimum: float = 0) -> float:
    value = (base + float(modifiers.base.get(stat, 0))) * (1 + float(modifiers.proportional.get(stat, 0)))
    return max(value * family_factor(modifiers, stat) + float(modifiers.flat.get(stat, 0)), minimum)


def _additive_scalar(base: float, stat: str, modifiers: ResolvedStats, *, minimum: float = 0) -> float:
    return max(base + float(modifiers.proportional.get(stat, 0)) + float(modifiers.base.get(stat, 0)) + float(modifiers.flat.get(stat, 0)), minimum)


def _combined(upgrades: ResolvedStats, evolutions: ResolvedStats) -> ResolvedStats:
    total = ResolvedStats()
    merge(total, upgrades)
    merge(total, evolutions)
    return total


def _base_damage(context: CalculationContext, attack: Attack, evolutions: ResolvedStats) -> tuple[Dist, Dist]:
    strength = float(context.state.ability_strength) if {"exalted", "pseudo_exalted"} & context.weapon.traits else 1.0
    raw = attack.stats.damage * max(strength, 0)
    conversion = sum(float(bucket.get("impact_to_puncture_conversion", 0)) for bucket in (evolutions.proportional, evolutions.base, evolutions.flat))
    if conversion > 0 and raw.get("impact", 0):
        moved = raw.get("impact", 0) * min(conversion, 1)
        raw += Dist(impact=-moved, puncture=moved)
    original = Dist(raw)
    flat = float(evolutions.base.get("damage", 0))
    if flat and raw.total: raw += Dist({kind: flat * raw.weight(kind) for kind in raw})
    return raw, original


def _modified_damage(base: Dist, resolved: ResolvedStats) -> Dist:
    recorded = resolved.proportional.get("damage", Dist())
    modifiers = {kind: float(value) for kind, value in recorded.items()} if isinstance(recorded, Dist) else {}
    modifiers.update({kind: float(value) for kind, value in resolved.proportional.items() if kind in DAMAGE_TYPES})
    return base.apply_modifiers(modifiers)


def _damage(attack: Attack, base: Dist, original: Dist, upgrades: ResolvedStats, evolutions: ResolvedStats) -> Dist:
    total = _combined(upgrades, evolutions)
    evolved = _modified_damage(base, total)
    original_modified = _modified_damage(original, total)
    common = max(1 + attack.stats.damage_bonus + float(total.proportional.get("damage_bonus", 0)), 0)
    status_bonus = family_bonus(total, "unique_status", "damage_bonus")
    if attack.stats.co_effect == "multiplies":
        damage = evolved * common * max(1 + status_bonus, 1)
    else:
        damage = evolved * common + original_modified * max(status_bonus, 0)
    for family, stats in total.families.items():
        if family in {"unique_status", "non_critical_hit", "multishot_ammo", *DEFERRED_FAMILIES}: continue
        damage *= max(1 + float(stats.get("damage_bonus", 0)), 1)
    return damage


def _dot_base_damage(attack: Attack, base: Dist, original: Dist, upgrades: ResolvedStats, evolutions: ResolvedStats) -> float:
    total = _combined(upgrades, evolutions)
    common = max(1 + attack.stats.damage_bonus + float(total.proportional.get("damage_bonus", 0)), 0)
    status_bonus = family_bonus(total, "unique_status", "damage_bonus")
    value = base.total * common * max(1 + status_bonus, 1) if attack.stats.co_effect == "multiplies" else base.total * common + original.total * max(status_bonus, 0)
    for family, stats in total.families.items():
        if family in {"unique_status", "non_critical_hit", "multishot_ammo", *DEFERRED_FAMILIES}: continue
        value *= max(1 + float(stats.get("damage_bonus", 0)), 1)
    return value


def _elemental_dot_bonuses(total: ResolvedStats) -> Stats:
    modifiers = total.proportional.get("damage", Dist())
    heat = float(modifiers.get("heat", 0)) if isinstance(modifiers, Dist) else 0
    electricity = float(modifiers.get("electricity", 0)) if isinstance(modifiers, Dist) else 0
    toxin = float(modifiers.get("toxin", 0)) if isinstance(modifiers, Dist) else 0
    return Stats(heat=max(1 + heat, 0), electricity=max(1 + electricity, 0), toxin=max(1 + toxin, 0), gas=max(1 + heat + toxin, 0), slash=1.0)


def _status_vulnerability(effects: Iterable[ResolvedEffect]) -> float:
    return max(1 + sum(float(effect.value) for effect in effects if effect.stat == "status_vulnerability"), 0)


def _derived_chances(crit: float, status: float, total: ResolvedStats) -> tuple[float, float]:
    crit_conversion = sum(float(bucket.get("crit_from_status", 0)) for bucket in (total.proportional, total.base, total.flat))
    status_conversion = sum(float(bucket.get("status_from_crit", 0)) for bucket in (total.proportional, total.base, total.flat))
    if crit_conversion:
        value = status * crit_conversion
        crit += min(value, total.maximums.get("crit_from_status", value))
    if status_conversion:
        value = crit * status_conversion
        status += min(value, total.maximums.get("status_from_crit", value))
    return max(crit, 0), max(status, 0)


def _stance(context: CalculationContext) -> Upgrade | None:
    return next((upgrade for upgrade in context.loadout.upgrades if upgrade.slot == "stance"), None)


def _stance_combo(context: CalculationContext, attack: Attack) -> Mapping[str, Any] | None:
    stance = _stance(context)
    if stance is None: return None
    if attack.category in HEAVY_CATEGORIES: key = "heavy"
    elif attack.category == "slide": key = "slide"
    elif attack.category == "slam": key = "slam"
    else: key = str(context.state.stance_combo)
    return stance.combos.get(key) or stance.combos.get("neutral")


def _multishot_ammo_bonus(total: ResolvedStats) -> float:
    return family_bonus(total, "multishot_ammo", "damage_bonus")


def _ranged_rate(context: CalculationContext, attack: Attack, total: ResolvedStats, multishot: float) -> tuple[float, float, Stats]:
    locked = bool(total.proportional.get("fire_rate_lock"))
    scale = 1.0 if locked else 1 + float(total.proportional.get("fire_rate", 0))
    fire_rate = max(float(attack.stats.fire_rate) * scale, 0.05)
    if not locked: fire_rate *= family_factor(total, "fire_rate")
    burst_count = max(float(attack.stats.burst_count), 1)
    burst_delay = max(float(attack.stats.burst_delay), 0) / max(scale, 1)
    charge_time = max(float(attack.stats.charge_time), 0) / max(scale, 0.01) / (family_factor(total, "fire_rate") if not locked else 1)
    incarnon = attack.form == "incarnon" and context.weapon.incarnon_charges is not None
    magazine_base = float(context.weapon.incarnon_charges) if incarnon else float(context.weapon.magazine_size)
    magazine = max(true_round(magazine_base if incarnon else (magazine_base + float(total.base.get("magazine_capacity", 0))) * (1 + float(total.proportional.get("magazine_capacity", 0))) + float(total.flat.get("magazine_capacity", 0))), 1)
    efficiency = 0.0 if incarnon else clamp(float(total.proportional.get("ammo_efficiency", 0)), 0, 1)
    ammo_cost = max(float(attack.stats.ammo_cost), 0)
    consumes_multishot = _multishot_ammo_bonus(total) != 0
    if consumes_multishot: ammo_cost *= max(multishot, 1)
    reload_time = float(context.weapon.reload_time) / max(1 + float(total.proportional.get("reload_speed", 0)), 0.01)
    if context.weapon.recharge_rate is not None and not incarnon:
        recharge_rate = max(float(context.weapon.recharge_rate), 0)
        reload_time += float("inf") if recharge_rate == 0 else magazine / recharge_rate
    if ammo_cost <= 0 or efficiency >= 1:
        sustained = fire_rate
    else:
        shots = magazine / ammo_cost
        bursts = shots / burst_count
        ammo_spent = 1 - efficiency
        cycle = bursts * (charge_time + (burst_count - 1) * burst_delay)
        cycle += (bursts - ammo_spent) / fire_rate + ammo_spent * reload_time
        sustained = float("inf") if cycle <= 0 else shots / cycle
    return fire_rate, sustained, Stats(ammo_cost=ammo_cost, ammo_efficiency=efficiency, magazine_capacity=magazine, reload_time=reload_time, burst_count=burst_count, burst_delay=burst_delay, charge_time=charge_time)


def _melee_rate(context: CalculationContext, attack: Attack, total: ResolvedStats) -> tuple[float, Stats]:
    heavy = attack.category in HEAVY_CATEGORIES
    speed_bonus = float(total.proportional.get("heavy_attack_speed" if heavy else "attack_speed", 0))
    base_speed = float(attack.stats.fire_rate if attack.stats.attack_speed is None else attack.stats.attack_speed)
    speed = max(base_speed * (1 + speed_bonus), 0)
    combo = _stance_combo(context, attack)
    if combo and float(combo.get("duration", 0)) > 0 and float(combo.get("hits", 0)) > 0:
        speed *= float(combo["hits"]) / float(combo["duration"])
    return speed, Stats(attack_speed=speed, heavy_attack_speed=max(1 + float(total.proportional.get("heavy_attack_speed", 0)), 0), heavy_attack_efficiency=max(float(attack.stats.heavy_attack_efficiency) + float(total.proportional.get("heavy_attack_efficiency", 0)), 0), initial_combo=max(float(attack.stats.initial_combo) + float(total.proportional.get("initial_combo", 0)), 0))


def _provisional(context: CalculationContext, attack: Attack, upgrade_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...]) -> tuple[Stats, StatusModel]:
    upgrades = aggregate(effect for effect in upgrade_effects if not effect.automatic)
    evolutions = aggregate(effect for effect in evolution_effects if not effect.automatic)
    total = _combined(upgrades, evolutions)
    base, original = _base_damage(context, attack, evolutions)
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


def _resolve_effects(context: CalculationContext, attack: Attack, source: tuple[ResolvedEffect, ...], provisional: Stats, model: StatusModel, equipped: set[str]) -> tuple[list[ResolvedEffect], list[ResolvedEffect]]:
    resolved: list[ResolvedEffect] = []
    positions: list[ResolvedEffect] = []
    for effect in source:
        current = evaluate(effect, context=context, attack=attack, stats=provisional, status=model, equipped=equipped)
        if current is None: continue
        event = automatic_value(current, "on")
        if event in POSITION_EVENTS:
            positions.append(current)
        else:
            resolved.append(current)
    return resolved, positions


def _forced_procs(attack: Attack, effects: Iterable[ResolvedEffect]) -> Dist:
    forced = attack.stats.forced_procs
    for effect in effects:
        if effect.stat not in PROC_STATS or automatic_value(effect, "on") is not None: continue
        forced += Dist({effect.stat.removesuffix("_proc"): float(effect.value)})
    return forced


def _status_model(damage: Dist, forced_procs: Dist, status_chance: float, attempts: float, attacks_per_second: float, duration: float, effects: Iterable[ResolvedEffect], crit_chance: float, *, include_random: bool = True, afflictions: bool = False) -> StatusModel:
    effects = tuple(effects)
    base = StatusModel(damage, forced_procs, status_chance, attempts, attacks_per_second, duration)
    direct_counts: dict[str, float] = {}
    direct_probabilities: dict[str, float] = {}
    critical_counts: dict[str, float] = {}
    for effect in effects:
        if effect.stat not in PROC_STATS or automatic_value(effect, "on") != "critical_hit": continue
        kind = effect.stat.removesuffix("_proc")
        chance = clamp(float(effect.value) * min(max(crit_chance, 0), 1), 0, 1)
        direct_counts[kind] = direct_counts.get(kind, 0) + chance
        direct_probabilities[kind] = 1 - (1 - direct_probabilities.get(kind, 0)) * (1 - chance)
        critical_counts[kind] = critical_counts.get(kind, 0) + chance * max(attempts, 0)

    direct_any_per_attempt = 1 - _product(1 - probability for probability in direct_probabilities.values())
    triggered_counts: dict[str, float] = {}
    triggered_probabilities: dict[str, float] = {}
    for effect in effects:
        event = "impact_status_proc" if effect.stat == "bleed_on_impact" else automatic_value(effect, "on")
        if effect.stat not in PROC_STATS and effect.stat != "bleed_on_impact": continue
        if event == "any_status_proc":
            source_probability = 1 - (1 - base.base_any_proc_probability_per_attempt()) * (1 - direct_any_per_attempt)
        elif isinstance(event, str) and event.endswith("_status_proc"):
            source = event.removesuffix("_status_proc")
            source_probability = base.base_proc_probability_per_attempt(source)
            source_probability = 1 - (1 - source_probability) * (1 - direct_probabilities.get(source, 0))
        else:
            continue
        kind = "slash" if effect.stat == "bleed_on_impact" else effect.stat.removesuffix("_proc")
        chance = clamp(float(effect.value) * source_probability, 0, 1)
        triggered_counts[kind] = triggered_counts.get(kind, 0) + chance
        triggered_probabilities[kind] = 1 - (1 - triggered_probabilities.get(kind, 0)) * (1 - chance)

    extra_per_attempt = {kind: direct_counts.get(kind, 0) + triggered_counts.get(kind, 0) for kind in set(direct_counts) | set(triggered_counts)}
    extra_probabilities_per_attempt = {
        kind: 1 - (1 - direct_probabilities.get(kind, 0)) * (1 - triggered_probabilities.get(kind, 0))
        for kind in set(direct_probabilities) | set(triggered_probabilities)
    }
    extra_counts = Dist({kind: count * max(attempts, 0) for kind, count in extra_per_attempt.items()})
    extra_probabilities = Dist({kind: attack_proc_chance(probability, max(attempts, 0)) for kind, probability in extra_probabilities_per_attempt.items()})
    extra_any_per_attempt = 1 - _product(1 - probability for probability in extra_probabilities_per_attempt.values())
    extra_any_probability = attack_proc_chance(extra_any_per_attempt, max(attempts, 0))
    any_per_attempt = 1 - (1 - base.base_any_proc_probability_per_attempt()) * (1 - extra_any_per_attempt)
    random_chance = clamp(sum(float(effect.value) for effect in effects if include_random and effect.stat == "random_proc" and automatic_value(effect, "on") == "any_status_proc"), 0, 1)
    random_probability = attack_proc_chance(random_chance * any_per_attempt, max(attempts, 0))

    random_triggered: dict[str, float] = {}
    if random_probability > 0:
        for effect in effects:
            if effect.stat not in PROC_STATS: continue
            event = automatic_value(effect, "on")
            if not isinstance(event, str) or not event.endswith("_status_proc"): continue
            source = event.removesuffix("_status_proc")
            if source not in RANDOM_STATUS_TYPES: continue
            kind = effect.stat.removesuffix("_proc")
            chance = random_probability / len(RANDOM_STATUS_TYPES) * clamp(float(effect.value), 0, 1)
            chance *= 1 - extra_probabilities.get(kind, 0)
            random_triggered[kind] = random_triggered.get(kind, 0) + chance
    random_triggered_procs = Dist(random_triggered)
    extra_counts += random_triggered_procs
    extra_probabilities += random_triggered_procs

    provisional = StatusModel(damage, forced_procs, status_chance, attempts, attacks_per_second, duration, extra_counts, extra_probabilities, extra_any_probability, random_probability, random_triggered_procs, Dist(critical_counts))
    debilitate = clamp(sum(float(effect.value) for effect in effects if effect.stat == "debilitate_proc_chance"), 0, 1)
    if debilitate:
        additions: dict[str, float] = {}
        for combined, components in COMBINED_STATUS_COMPONENTS.items():
            activation = min(provisional.expected_stacks(combined, 10) / 10, 1)
            produced = provisional.proc_count_per_attack(combined) * debilitate * activation / len(components)
            for component in components: additions[component] = additions.get(component, 0) + produced
        extra_counts += Dist(additions)
        extra_probabilities += Dist({kind: min(value, 1) for kind, value in additions.items()})

    if afflictions:
        multiplier = sum(float(effect.value) for effect in effects if effect.stat == "afflictions_proc_multiplier")
        existing = StatusModel(damage, forced_procs, status_chance, attempts, attacks_per_second, duration, extra_counts, extra_probabilities, extra_any_probability, random_probability, random_triggered_procs, Dist(critical_counts))
        copied = Dist({kind: existing.proc_count_per_attack(kind) * multiplier for kind in RANDOM_STATUS_TYPES | {"void"}})
        extra_counts += copied
        critical_counts = {kind: value * (1 + multiplier) for kind, value in critical_counts.items()}

    return StatusModel(damage, forced_procs, status_chance, attempts, attacks_per_second, duration, extra_counts, extra_probabilities, extra_any_probability, random_probability, random_triggered_procs, Dist(critical_counts))


def _product(values: Iterable[float]) -> float:
    result = 1.0
    for value in values: result *= value
    return result


def _with_random_proc(model: StatusModel, effects: Iterable[ResolvedEffect], probability: float) -> StatusModel:
    triggered: dict[str, float] = {}
    for effect in effects:
        if effect.stat not in PROC_STATS: continue
        event = automatic_value(effect, "on")
        if not isinstance(event, str) or not event.endswith("_status_proc"): continue
        source = event.removesuffix("_status_proc")
        if source not in RANDOM_STATUS_TYPES: continue
        kind = effect.stat.removesuffix("_proc")
        triggered[kind] = triggered.get(kind, 0) + probability / len(RANDOM_STATUS_TYPES) * clamp(float(effect.value), 0, 1)
    random_triggered = Dist(triggered)
    return StatusModel(model.damage, model.forced_procs, model.status_chance, model.attempts_per_attack, model.attacks_per_second, model.duration, model.extra_proc_counts + random_triggered, model.extra_proc_probabilities + random_triggered, model.extra_any_proc_probability, probability, random_triggered, model.critical_proc_counts)


def _special_value(effects: Iterable[ResolvedEffect], stat: str, event: str | None = None) -> float:
    return sum(float(effect.value) for effect in effects if effect.stat == stat and (event is None or automatic_value(effect, "on") == event))


def _hit_multiplier(chance: float, tier_bonus: float, damage: float, non_crit_damage: float = 0, non_crit_chance: float = 0) -> float:
    return hit_multiplier(chance, damage, non_crit_damage, non_crit_chance) + tier_bonus * (damage - 1)


def _faction_factor(context: CalculationContext, total: ResolvedStats) -> float:
    if context.target.faction not in {"corpus", "grineer", "infested", "orokin", "murmur", "sentient"}: return 1.0
    return 1 + float(total.proportional.get(f"{context.target.faction}_damage", 0))


def _is_aoe_attack(attack: Attack) -> bool:
    return bool(attack.aoe or attack.category in SLAM_CATEGORIES)


def _spatial_falloff(attack: Attack, effective: EffectiveAttackStats) -> tuple[float, SpatialMetrics]:
    falloff = attack.stats.falloff
    start_range = float(effective.start_range)
    end_range = float(effective.end_range)
    max_range = effective.max_range
    final_multiplier = float(effective.final_multiplier)
    if _is_aoe_attack(attack):
        if "end_range" not in falloff: return 1.0, SpatialMetrics()
        falloff_multiplier = average_falloff_multiplier(start_range, end_range, final_multiplier)
        damage_mass = aoe_damage_mass(start_range, end_range, final_multiplier)
        return falloff_multiplier, SpatialMetrics(falloff_multiplier=falloff_multiplier, damage_mass=damage_mass, dimension=3)
    falloff_multiplier = ranged_falloff_multiplier(start_range, end_range, float(max_range), final_multiplier) if max_range is not None and "end_range" in falloff else 1.0
    return falloff_multiplier, SpatialMetrics(falloff_multiplier=falloff_multiplier)


def _set_zone_damage(average: AverageAttackStats, spatial: SpatialMetrics, zone: str, fields: tuple[str, ...], direct: float, dot: float) -> None:
    average_direct = direct * average.falloff_multiplier
    average_dot = dot * average.falloff_multiplier
    setattr(average, fields[0], average_direct)
    setattr(average, fields[1], average_dot)
    if spatial.damage_mass is None:
        setattr(spatial, fields[0], None)
        setattr(spatial, fields[1], None)
    else:
        setattr(spatial, fields[0], direct * spatial.damage_mass)
        setattr(spatial, fields[1], dot * spatial.damage_mass)


def _refresh_spatial(metrics: SpatialMetrics, fire_rate: float) -> None:
    for fields in ZONE_FIELDS.values():
        direct = getattr(metrics, fields[0])
        dot = getattr(metrics, fields[1])
        if direct is None or dot is None:
            for field in fields: setattr(metrics, field, None)
            continue
        setattr(metrics, fields[2], direct + dot)
        setattr(metrics, fields[3], direct * fire_rate)
        setattr(metrics, fields[4], dot * fire_rate)
        setattr(metrics, fields[5], (direct + dot) * fire_rate)


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
        proc_model = _status_model(damage, effective.forced_procs, float(effective.status_chance), shots, average.sustained_fire_rate, float(effective.status_duration), source_effects, chance, include_random=False, afflictions=afflictions)
        if effective.status_model.random_proc_probability: proc_model = _with_random_proc(proc_model, source_effects, effective.status_model.random_proc_probability)
    value = 0.0
    dot_base = float(effective.dot_base_damage) * damage_factor
    status_damage = float(effective.status_damage)
    for kind, factor in DOT_MULTIPLIERS.items():
        target_factor = damage_multiplier(context.target, kind, zone=zone, dot=True, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects)
        if target_factor is None: continue
        proc_count = proc_model.proc_count_per_attack(kind)
        if kind == "gas" and average.sustained_fire_rate > 0 and effective.status_duration > 0:
            proc_count = min(proc_model.proc_rate(kind) * float(effective.status_duration), 10) / (average.sustained_fire_rate * float(effective.status_duration))
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
    mixed = {fields[index]: 0.0 for fields in ZONE_FIELDS.values() for index in (0, 1)}
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
        for zone, fields in ZONE_FIELDS.items():
            damage = _zone_damage(context, result, zone, direct_hits=multishot, dot_multishot=multishot, damage_factor=damage_factor)
            if damage is None: continue
            direct, dot = damage
            mixed[fields[0]] += direct * weight
            mixed[fields[1]] += dot * weight
    for zone, fields in ZONE_FIELDS.items(): _set_zone_damage(average, spatial, zone, fields, mixed[fields[0]], mixed[fields[1]])
    first = [effect for effect in effects if automatic_value(effect, "on") == "magazine_first_shot" and effect.stat == "damage_bonus"]
    first_factor = 1.0
    for family in {effect.family for effect in first}: first_factor *= 1 + sum(float(effect.value) for effect in first if effect.family == family)
    first_weight = next((weight for events, weight in weights if "magazine_first_shot" in events), 0)
    average.first_shot_damage_multiplier = 1 + (first_factor - 1) * first_weight
    refresh_metrics(average)
    _refresh_spatial(spatial, average.sustained_fire_rate)


def _calculate_attack(context: CalculationContext, attack: Attack, upgrade_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...], *, automatic_model_override: StatusModel | None = None, status_effects_override: dict[str, float] | None = None, random_proc_probability: float = 0) -> AttackResult:
    provisional, provisional_model = _provisional(context, attack, upgrade_effects, evolution_effects)
    equipped = {upgrade.name for upgrade in context.loadout.upgrades}
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
    total = _combined(upgrades, evolutions)
    base_damage, original = _base_damage(context, attack, evolutions)
    damage = _damage(attack, base_damage, original, upgrades, evolutions)
    heavy = context.weapon.type == "melee" and attack.category in HEAVY_CATEGORIES
    upgrade_crit = float(upgrades.proportional.get("crit_chance", 0)) * (2 if heavy else 1)
    crit_base = float(attack.stats.crit_chance) + float(total.base.get("crit_chance", 0))
    crit = max(crit_base * (1 + upgrade_crit + float(evolutions.proportional.get("crit_chance", 0))) * family_factor(total, "crit_chance") + float(total.flat.get("crit_chance", 0)), 0)
    resolved_effects = (*upgrades_resolved, *evolution_resolved)
    status = _scalar(float(attack.stats.status_chance), "status_chance", total) * _status_vulnerability(resolved_effects)
    crit, status = _derived_chances(crit, status, total)
    if context.weapon.type == "melee" and attack.category == "slide": crit *= max(1 + float(total.proportional.get("slide_crit_chance", 0)), 0)
    crit_damage = _scalar(float(attack.stats.crit_damage), "crit_damage", total, minimum=1)
    doughty = next((effect for effect in (*upgrades_resolved, *evolution_resolved) if effect.stat == "crit_damage" and automatic_value(effect, "with") == "puncture_status_chance"), None)
    doughty_bonus = 0.0
    weakpoint_common = float(total.proportional.get("weakpoint_crit_chance", 0))
    weakpoint_family = sum(float(family.get("weakpoint_crit_chance", 0)) for family in total.families.values())
    weakpoint_crit = 0.0 if context.weapon.type == "melee" else max(crit + float(attack.stats.crit_chance) * (weakpoint_common + weakpoint_family) + float(total.flat.get("weakpoint_crit_chance", 0)), 0)
    crit_tier_chance = clamp(_special_value((*upgrades_resolved, *evolution_resolved), "crit_tier", "critical_hit"), 0, 1)
    ms_bonus = 0 if context.weapon.type == "melee" or total.proportional.get("multishot_lock") else float(total.proportional.get("multishot", 0))
    ms_ammo_bonus = _multishot_ammo_bonus(total)
    if attack.delivery == "beam" and ms_ammo_bonus and not total.proportional.get("multishot_lock"): ms_bonus *= 1 + ms_ammo_bonus
    multishot = max(float(attack.stats.multishot) * (1 + ms_bonus), 1)
    if attack.delivery != "beam" and ms_ammo_bonus: damage *= 1 + ms_ammo_bonus * (1 - 1 / multishot)
    if context.weapon.type == "melee":
        instant_rate, category_stats = _melee_rate(context, attack, total)
        fire_rate = instant_rate
        stance = _stance_combo(context, attack)
        if stance: damage *= max(float(stance.get("multiplier", 1)), 0)
        if attack.category in SLAM_CATEGORIES: damage *= max(1 + float(total.proportional.get("slam_damage", 0)), 0)
    else:
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
    puncture_bonus = 0 if _is_aoe_attack(attack) else 0.05 * puncture_stacks
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
    effective = EffectiveAttackStats(damage=damage, dot_base_damage=_dot_base_damage(attack, base_damage, original, upgrades, evolutions), dot_elemental_bonuses=_elemental_dot_bonuses(total), forced_procs=forced, status_model=status_model, crit_chance=crit, weakpoint_crit_chance=weakpoint_crit, crit_damage=crit_damage, status_chance=status, status_duration=duration, status_damage=max(1 + float(total.proportional.get("status_damage", 0)), 1), multishot=multishot, instantaneous_fire_rate=instant_rate, attack_event_rate=fire_rate, faction_damage=faction, target_vulnerability=max(1 + float(total.proportional.get("unique_enemy_vulnerability_multiplier", 0)), 0), overguard_damage_multiplier=overguard_effect if overguard_effect else 1, non_crit_bonus_damage=non_crit_damage, non_crit_bonus_chance=non_crit_chance, weakpoint_damage_bonus=weakpoint_bonus, special_effects=tuple(resolved_effects), **category_stats)
    for stat in ("range", "punch_through", "accuracy", "recoil", "zoom", "ammo_maximum"):
        base_value = float(getattr(attack.stats, stat, 0)) if hasattr(attack.stats, stat) else 0
        effective[stat] = _additive_scalar(base_value, stat, total) if stat == "punch_through" else _scalar(base_value, stat, total)
    projectile_speed = max(1 + float(total.proportional.get("projectile_speed", 0)), 0)
    effective.projectile_speed = projectile_speed
    radius_bonus = float(total.proportional.get("explosion_radius", 0)) + (float(total.proportional.get("slam_radius", 0)) if attack.category in SLAM_CATEGORIES else 0)
    range_scale = max(1 + radius_bonus, 0) if _is_aoe_attack(attack) else projectile_speed
    effective.start_range = float(attack.stats.falloff.get("start_range", 0)) * range_scale
    effective.end_range = float(attack.stats.falloff.get("end_range", 0)) * range_scale
    maximum = attack.stats.max_range
    if maximum is None and "end_range" in attack.stats.falloff: maximum = float(attack.stats.falloff["end_range"])
    effective.max_range = None if maximum is None else float(maximum) * range_scale
    final_multiplier = attack.stats.falloff.get("final_multiplier")
    effective.final_multiplier = 1.0 if final_multiplier is None else float(final_multiplier)
    effective.noise_level = total.proportional.get("noise_level", attack.stats.noise_level)
    base = BaseAttackStats(damage=base_damage, forced_procs=attack.stats.forced_procs, crit_chance=attack.stats.crit_chance, crit_damage=attack.stats.crit_damage, status_chance=attack.stats.status_chance, status_duration=attack.stats.status_duration, multishot=attack.stats.multishot, fire_rate=attack.stats.fire_rate)
    modded = ModdedAttackStats(damage=damage, crit_chance=crit, crit_damage=crit_damage, status_chance=status, status_duration=duration, multishot=multishot, fire_rate=instant_rate, **category_stats)
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
    falloff_multiplier, spatial = _spatial_falloff(attack, effective)
    average = AverageAttackStats(crit_chance=body_crit, crit_multiplier=crit_multiplier(body_crit + body_tier_bonus, crit_damage), weakpoint_crit_chance=weak_crit, weakpoint_crit_multiplier=crit_multiplier(weak_crit + weak_tier_bonus, crit_damage), sustained_fire_rate=fire_rate, procs_per_shot=status_model.expected_procs_per_attack, melee_duplicate_multiplier=duplicate_multiplier, melee_doughty_bonus=doughty_bonus, crit_tier_bonus=body_tier_bonus, weakpoint_crit_tier_bonus=weak_tier_bonus, secondary_enervate_bonus=body_bonus, weakpoint_secondary_enervate_bonus=weak_bonus, falloff_multiplier=falloff_multiplier)
    result = AttackResult(attack.name, attack, base, modded, effective, upgrades, evolutions, average, spatial, status_effects, list(attack.children), original)
    combo_multiplier = 1
    if heavy:
        combo_multiplier = max(1, min(int(context.weapon.combo.get("max_combo", 12)), int(context.state.combo)))
    average.combo_multiplier = combo_multiplier
    for zone, fields in ZONE_FIELDS.items():
        zone_damage = _zone_damage(context, result, zone, direct_hits=1 if context.weapon.type == "melee" else multishot, duplicate_multiplier=duplicate_multiplier, combo_multiplier=combo_multiplier)
        if zone_damage is None:
            setattr(average, fields[0], None)
            setattr(average, fields[1], None)
            continue
        direct, dot = zone_damage
        _set_zone_damage(average, spatial, zone, fields, direct, dot)
    refresh_metrics(average)
    _refresh_spatial(spatial, average.sustained_fire_rate)
    _apply_position_mixture(context, result, [*upgrade_positions, *evolution_positions])
    return result


class AttackCalculator:
    __slots__ = ("context", "upgrade_effects", "evolution_effects")

    def __init__(self, context: CalculationContext, upgrade_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...]) -> None:
        self.context = context
        self.upgrade_effects = upgrade_effects
        self.evolution_effects = evolution_effects

    def calculate(self, attack: Attack, *, automatic_model: StatusModel | None = None, status_effects: dict[str, float] | None = None, random_proc_probability: float = 0) -> AttackResult:
        return _calculate_attack(self.context, attack, self.upgrade_effects, self.evolution_effects, automatic_model_override=automatic_model, status_effects_override=status_effects, random_proc_probability=random_proc_probability)
