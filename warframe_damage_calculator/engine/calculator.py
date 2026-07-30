from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from ..domain.damage import Dist
from ..domain.results import AttackResult, DensityMetrics, Metrics, ResolvedStats, Stats
from ..domain.upgrades import ResolvedEffect, Upgrade, UpgradeStats
from .aggregation import DAMAGE_TYPES, aggregate, merge
from .effects import evaluate
from .formulas import DOT_MULTIPLIERS, aoe_damage_mass, average_falloff_multiplier, clamp, crit_multiplier, family_bonus, family_factor, hit_multiplier, punch_through_damage_mass, refresh_metrics, true_round
from .special import automatic_value, automatic_values, average_enervate_bonus, enervate_parameters
from .status import StatusModel
from .targets import ZONE_FIELDS, damage_multiplier, damage_total


HEAVY_CATEGORIES = frozenset({"heavy", "heavy_slam"})
SLAM_CATEGORIES = frozenset({"slam", "heavy_slam"})
POSITION_EVENTS = frozenset({"magazine_first_shot", "magazine_last_shot"})
DEFERRED_STATS = frozenset({"duplicated_hit", "random_proc", "crit_reset_charges", "crit_tier"})
DEFERRED_FAMILIES = frozenset({"magazine_first_shot", "magazine_last_shot"})
PROC_STATS = frozenset(f"{damage_type}_proc" for damage_type in DAMAGE_TYPES)
DENSITY_FIELDS = {"normal": "damage_density", "weakpoint": "weakpoint_damage_density", "resistant": "resistant_damage_density"}


def _scalar(base: float, stat: str, build: ResolvedStats, *, minimum: float = 0) -> float:
    value = (base + float(build.base.get(stat, 0))) * (1 + float(build.proportional.get(stat, 0)))
    return max(value * family_factor(build, stat) + float(build.flat.get(stat, 0)), minimum)


def _additive_scalar(base: float, stat: str, build: ResolvedStats, *, minimum: float = 0) -> float:
    return max(base + float(build.proportional.get(stat, 0)) + float(build.base.get(stat, 0)) + float(build.flat.get(stat, 0)), minimum)


def _combined(build: ResolvedStats, evolutions: ResolvedStats) -> ResolvedStats:
    total = ResolvedStats()
    merge(total, build)
    merge(total, evolutions)
    return total


def _runtime_evolution_effects(weapon: Any) -> tuple[ResolvedEffect, ...]:
    selected = {str(tier): str(perk) for tier, perk in dict(weapon.runtime.evolutions).items()}
    choices = {"1": "1"} | selected
    effects: list[ResolvedEffect] = []
    for tier, perk in choices.items():
        record = weapon.evolutions.get(tier, {}).get(perk)
        if record is None: continue
        stats = UpgradeStats.from_record(record.get("stats", {}))
        runtime = {field: getattr(weapon.runtime, field) for field in stats.manual_fields}
        effects.extend(Upgrade(name=f"{weapon.name} evolution {tier}.{perk}", stats=stats, runtime=runtime).resolve_manual())
    return tuple(effects)


def _base_damage(weapon: Any, attack: Any, evolutions: ResolvedStats) -> tuple[Dist, Dist]:
    strength = float(weapon.runtime.ability_strength) if {"exalted", "pseudo_exalted"} & weapon.traits else 1.0
    raw = attack.stats.damage * max(strength, 0)
    conversion = sum(float(bucket.get("impact_to_puncture_conversion", 0)) for bucket in (evolutions.proportional, evolutions.base, evolutions.flat))
    if conversion > 0 and raw.get("impact", 0):
        moved = raw.get("impact", 0) * min(conversion, 1)
        raw += Dist(impact=-moved, puncture=moved)
    original = Dist(raw)
    flat = float(evolutions.base.get("damage", 0))
    if flat and raw.total: raw += Dist({kind: flat * raw.weight(kind) for kind in raw})
    return raw, original


def _modified_damage(base: Dist, build: ResolvedStats) -> Dist:
    recorded = build.proportional.get("damage", Dist())
    modifiers = {kind: float(value) for kind, value in recorded.items()} if isinstance(recorded, Dist) else {}
    modifiers.update({kind: float(value) for kind, value in build.proportional.items() if kind in DAMAGE_TYPES})
    return base.apply_modifiers(modifiers)


def _damage(weapon: Any, attack: Any, base: Dist, original: Dist, build: ResolvedStats, evolutions: ResolvedStats) -> Dist:
    total = _combined(build, evolutions)
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


def _stance(weapon: Any) -> Any | None:
    return next((upgrade for upgrade in weapon.build if upgrade.slot == "stance"), None)


def _stance_combo(weapon: Any, attack: Any) -> dict[str, Any] | None:
    stance = _stance(weapon)
    if stance is None: return None
    if attack.category in HEAVY_CATEGORIES: key = "heavy"
    elif attack.category == "slide": key = "slide"
    elif attack.category == "slam": key = "slam"
    else: key = str(weapon.runtime.stance_combo)
    return stance.combos.get(key) or stance.combos.get("neutral")


def _multishot_ammo_bonus(total: ResolvedStats) -> float:
    return family_bonus(total, "multishot_ammo", "damage_bonus")


def _ranged_rate(weapon: Any, attack: Any, total: ResolvedStats, multishot: float) -> tuple[float, float, Stats]:
    locked = bool(total.proportional.get("fire_rate_lock"))
    scale = 1.0 if locked else 1 + float(total.proportional.get("fire_rate", 0))
    fire_rate = max(float(attack.stats.fire_rate) * scale, 0.05)
    if not locked: fire_rate *= family_factor(total, "fire_rate")
    burst_count = max(float(attack.stats.burst_count), 1)
    burst_delay = max(float(attack.stats.burst_delay), 0) / max(scale, 1)
    charge_time = max(float(attack.stats.charge_time), 0) / max(scale, 0.01) / (family_factor(total, "fire_rate") if not locked else 1)
    incarnon = attack.form == "incarnon" and weapon.incarnon_charges is not None
    magazine_base = float(weapon.incarnon_charges) if incarnon else float(weapon.magazine_size)
    magazine = max(true_round(magazine_base if incarnon else (magazine_base + float(total.base.get("magazine_capacity", 0))) * (1 + float(total.proportional.get("magazine_capacity", 0))) + float(total.flat.get("magazine_capacity", 0))), 1)
    efficiency = 0.0 if incarnon else clamp(float(total.proportional.get("ammo_efficiency", 0)), 0, 1)
    ammo_cost = max(float(attack.stats.ammo_cost), 0)
    consumes_multishot = _multishot_ammo_bonus(total) != 0
    if consumes_multishot: ammo_cost *= max(multishot, 1)
    reload_time = float(weapon.reload_time) / max(1 + float(total.proportional.get("reload_speed", 0)), 0.01)
    if weapon.recharge_rate is not None and not incarnon:
        recharge_rate = max(float(weapon.recharge_rate), 0)
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
    return fire_rate, sustained, Stats(ammo_cost=ammo_cost, ammo_efficiency=efficiency, magazine_capacity=magazine, reload_speed=reload_time, burst_count=burst_count, burst_delay=burst_delay, charge_time=charge_time)


def _melee_rate(weapon: Any, attack: Any, total: ResolvedStats) -> tuple[float, Stats]:
    heavy = attack.category in HEAVY_CATEGORIES
    speed_bonus = float(total.proportional.get("heavy_attack_speed" if heavy else "attack_speed", 0))
    base_speed = float(attack.stats.fire_rate if attack.stats.attack_speed is None else attack.stats.attack_speed)
    speed = max(base_speed * (1 + speed_bonus), 0)
    combo = _stance_combo(weapon, attack)
    if combo and float(combo.get("duration", 0)) > 0 and float(combo.get("hits", 0)) > 0:
        speed *= float(combo["hits"]) / float(combo["duration"])
    return speed, Stats(attack_speed=speed, heavy_attack_speed=max(1 + float(total.proportional.get("heavy_attack_speed", 0)), 0), heavy_attack_efficiency=max(float(attack.stats.heavy_attack_efficiency) + float(total.proportional.get("heavy_attack_efficiency", 0)), 0), initial_combo=max(float(attack.stats.initial_combo) + float(total.proportional.get("initial_combo", 0)), 0))


def _provisional(weapon: Any, attack: Any, build_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...]) -> tuple[Stats, StatusModel]:
    build = aggregate(effect for effect in build_effects if not effect.automatic)
    evolutions = aggregate(effect for effect in evolution_effects if not effect.automatic)
    total = _combined(build, evolutions)
    base, original = _base_damage(weapon, attack, evolutions)
    damage = _damage(weapon, attack, base, original, build, evolutions)
    crit = _scalar(float(attack.stats.crit_chance), "crit_chance", total)
    status = _scalar(float(attack.stats.status_chance), "status_chance", total)
    crit, status = _derived_chances(crit, status, total)
    ms_bonus = 0 if weapon.type == "melee" or total.proportional.get("multishot_lock") else float(total.proportional.get("multishot", 0))
    multishot = max(float(attack.stats.multishot) * (1 + ms_bonus), 1)
    if weapon.type == "melee":
        sustained, _ = _melee_rate(weapon, attack, total)
        instantaneous = sustained
    else:
        instantaneous, sustained, _ = _ranged_rate(weapon, attack, total, multishot)
    duration = _scalar(float(attack.stats.status_duration), "status_duration", total)
    stats = Stats(damage=damage, crit_chance=crit, status_chance=status, multishot=multishot, fire_rate=instantaneous, sustained_rate=sustained, status_duration=duration)
    return stats, StatusModel(damage, attack.stats.forced_procs, status, multishot, sustained, duration)


def _resolve_effects(weapon: Any, attack: Any, source: tuple[ResolvedEffect, ...], provisional: Stats, model: StatusModel, equipped: set[str]) -> tuple[list[ResolvedEffect], list[ResolvedEffect]]:
    resolved: list[ResolvedEffect] = []
    positions: list[ResolvedEffect] = []
    for effect in source:
        current = evaluate(effect, weapon=weapon, attack=attack, stats=provisional, status=model, equipped=equipped)
        if current is None: continue
        event = automatic_value(current, "on")
        if event in POSITION_EVENTS:
            positions.append(current)
        elif current.stat not in DEFERRED_STATS:
            resolved.append(current)
        else:
            resolved.append(current)
    return resolved, positions


def _forced_procs(attack: Any, effects: Iterable[ResolvedEffect]) -> Dist:
    forced = attack.stats.forced_procs
    for effect in effects:
        if effect.stat not in PROC_STATS or automatic_value(effect, "on") is not None: continue
        forced += Dist({effect.stat.removesuffix("_proc"): float(effect.value)})
    return forced


def _special_value(effects: Iterable[ResolvedEffect], stat: str, event: str | None = None) -> float:
    return sum(float(effect.value) for effect in effects if effect.stat == stat and (event is None or automatic_value(effect, "on") == event))


def _hit_multiplier(chance: float, tier_bonus: float, damage: float, non_crit_damage: float = 0, non_crit_chance: float = 0) -> float:
    return hit_multiplier(chance, damage, non_crit_damage, non_crit_chance) + tier_bonus * (damage - 1)


def _faction_factor(weapon: Any, total: ResolvedStats) -> float:
    if weapon.target is None:
        return 1 + max(float(total.proportional.get(f"{name}_damage", 0)) for name in ("corpus", "grineer", "infested", "orokin", "murmur", "sentient"))
    if weapon.target.faction not in {"corpus", "grineer", "infested", "orokin", "murmur", "sentient"}: return 1.0
    return 1 + float(total.proportional.get(f"{weapon.target.faction}_damage", 0))


def _spatial_falloff(attack: Any, effective: Stats) -> tuple[float, float]:
    falloff = attack.stats.falloff
    if "end_range" not in falloff: return 1.0, 0.0
    start_range = float(effective.start_range)
    end_range = float(effective.end_range)
    final_multiplier = float(effective.final_multiplier)
    falloff_multiplier = average_falloff_multiplier(start_range, end_range, final_multiplier)
    if attack.aoe:
        return falloff_multiplier, aoe_damage_mass(start_range, end_range, final_multiplier)
    punch_through = float(effective.punch_through)
    if punch_through > 0:
        return falloff_multiplier, punch_through_damage_mass(start_range, end_range, final_multiplier, punch_through)
    return falloff_multiplier, 0.0


def _set_zone_damage(average: Metrics, density: DensityMetrics, zone: str, fields: tuple[str, ...], direct: float, dot: float) -> None:
    setattr(average, fields[0], direct * average.falloff_multiplier)
    setattr(average, fields[1], dot * average.falloff_multiplier)
    setattr(density, DENSITY_FIELDS[zone], (direct + dot) * density.damage_mass if density.damage_mass > 0 else None)


def _refresh_density(metrics: DensityMetrics, fire_rate: float) -> None:
    for prefix in ("", "weakpoint_", "resistant_"):
        density = getattr(metrics, f"{prefix}damage_density")
        setattr(metrics, f"{prefix}damage_density_per_second", None if density is None else density * fire_rate)


def _dot_value(weapon: Any, result: AttackResult, zone: str, *, multishot: float | None = None, damage_factor: float = 1) -> float:
    effective, average = result.effective, result.average
    damage = effective.damage * damage_factor
    if damage.total <= 0: return 0.0
    shots = float(effective.multishot if multishot is None else multishot)
    chance = average.weakpoint_crit_chance if zone == "weakpoint" else average.crit_chance
    tier_bonus = average.weakpoint_crit_tier_bonus if zone == "weakpoint" else average.crit_tier_bonus
    crit = _hit_multiplier(chance, tier_bonus, float(effective.crit_damage), float(effective.non_crit_bonus_damage), float(effective.non_crit_bonus_chance))
    faction = float(effective.faction_damage)
    weakpoint_bonus = float(effective.weakpoint_damage_bonus)
    regular = 0.0
    forced = 0.0
    for kind, factor in DOT_MULTIPLIERS.items():
        target_factor = damage_multiplier(weapon.target, kind, zone=zone, dot=True, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects)
        if target_factor is None: continue
        regular += factor * damage.get(kind, 0) * damage.weight(kind) * target_factor * float(effective.status_chance)
        forced += factor * float(effective.forced_procs.get(kind, 0)) * damage.get(kind, 0) * target_factor
    regular_hits = shots * shots if result.attack.delivery == "beam" else shots
    value = (regular * regular_hits + forced * shots) * float(effective.status_duration) * float(effective.status_damage) * faction ** 2 * crit
    source_effects = list(effective.special_effects)
    slash_factor = DOT_MULTIPLIERS["slash"] * float(effective.status_duration)
    slash_target = damage_multiplier(weapon.target, "slash", zone=zone, dot=True, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects)
    if slash_target is None: slash_target = 0
    tick_scale = shots if result.attack.delivery == "beam" else 1
    slash_per_proc = slash_factor * damage.total * crit * float(effective.status_damage) * faction ** 2 * tick_scale * slash_target
    hunter_per_proc = slash_factor * damage.total * max(float(effective.crit_damage), crit) * float(effective.status_damage) * faction ** 2 * tick_scale * slash_target
    hunter = _special_value(source_effects, "slash_proc", "critical_hit")
    hunter_procs = hunter * min(chance, 1)
    impact_chance = _special_value(source_effects, "slash_proc", "impact_status_proc")
    impact_probability = damage.weight("impact") + float(effective.forced_procs.get("impact", 0))
    internal_procs = impact_probability * float(effective.status_chance) * impact_chance
    guaranteed, fractional = divmod(float(effective.status_chance), 1)
    impact_event = impact_probability * impact_chance
    internal_probability = 1 - (1 - impact_event) ** guaranteed * ((1 - fractional) + fractional * (1 - impact_event))
    overlap = hunter_procs * internal_probability * min(hunter_per_proc, slash_per_proc)
    extra = hunter_procs * hunter_per_proc + internal_procs * slash_per_proc - overlap
    value += extra * (1 if result.attack.delivery == "beam" else shots)
    if weapon.type == "secondary":
        encumber = _special_value(source_effects, "random_proc", "any_status_proc")
        proc_chance = 1 - (1 - encumber * min(float(effective.status_chance), 1)) ** shots
        random_target = sum(factor * float(damage_multiplier(weapon.target, kind, zone=zone, dot=True, weakpoint_bonus=weakpoint_bonus, status_effects=result.status_effects) or 0) for kind, factor in DOT_MULTIPLIERS.items())
        value += proc_chance * damage.total * tick_scale * random_target / 13 * float(effective.status_duration) * crit * float(effective.status_damage) * faction ** 2
    return value


def _position_weights(magazine: float, ammo_cost: float, efficiency: float) -> list[tuple[frozenset[str], float]]:
    if ammo_cost <= 0: return [(frozenset(), 1)]
    shots = max(magazine / ammo_cost, 1)
    if shots <= 1: return [(frozenset(POSITION_EVENTS), 1)]
    if efficiency >= 1: return [(frozenset({"magazine_first_shot"}), 1)]
    weight = 1 / shots
    return [(frozenset({"magazine_first_shot"}), weight), (frozenset({"magazine_last_shot"}), weight), (frozenset(), max(0, 1 - 2 * weight))]


def _apply_position_mixture(weapon: Any, result: AttackResult, effects: list[ResolvedEffect]) -> None:
    if weapon.type == "melee": return
    if not effects: return
    effective, average, density = result.effective, result.average, result.density
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
            direct_total = damage_total(effective.damage * damage_factor, weapon.target, zone=zone, weakpoint_bonus=float(effective.weakpoint_damage_bonus), status_effects=result.status_effects)
            if direct_total is None: continue
            chance = average.weakpoint_crit_chance if zone == "weakpoint" else average.crit_chance
            tier_bonus = average.weakpoint_crit_tier_bonus if zone == "weakpoint" else average.crit_tier_bonus
            direct = direct_total * multishot * float(effective.faction_damage) * _hit_multiplier(chance, tier_bonus, float(effective.crit_damage), float(effective.non_crit_bonus_damage), float(effective.non_crit_bonus_chance))
            mixed[fields[0]] += direct * weight
            mixed[fields[1]] += _dot_value(weapon, result, zone, multishot=multishot, damage_factor=damage_factor) * weight
    for zone, fields in ZONE_FIELDS.items(): _set_zone_damage(average, density, zone, fields, mixed[fields[0]], mixed[fields[1]])
    first = [effect for effect in effects if automatic_value(effect, "on") == "magazine_first_shot" and effect.stat == "damage_bonus"]
    first_factor = 1.0
    for family in {effect.family for effect in first}: first_factor *= 1 + sum(float(effect.value) for effect in first if effect.family == family)
    first_weight = next((weight for events, weight in weights if "magazine_first_shot" in events), 0)
    average.first_shot_damage_multiplier = 1 + (first_factor - 1) * first_weight
    refresh_metrics(average)
    _refresh_density(density, average.fire_rate)


def _calculate_attack(weapon: Any, attack: Any, build_effects: tuple[ResolvedEffect, ...], evolution_effects: tuple[ResolvedEffect, ...]) -> AttackResult:
    provisional, provisional_model = _provisional(weapon, attack, build_effects, evolution_effects)
    equipped = {upgrade.name for upgrade in weapon.build}
    all_source = (*build_effects, *evolution_effects)
    initial_build_effects, _ = _resolve_effects(weapon, attack, build_effects, provisional, provisional_model, equipped)
    initial_evolution_effects, _ = _resolve_effects(weapon, attack, evolution_effects, provisional, provisional_model, equipped)
    stable = lambda effect: not any(str(value).endswith("_status_proc") for value in automatic_values(effect, "when"))
    initial_build = aggregate(effect for effect in initial_build_effects if stable(effect) and effect.stat not in DEFERRED_STATS)
    initial_evolutions = aggregate(effect for effect in initial_evolution_effects if stable(effect) and effect.stat not in DEFERRED_STATS)
    initial_total = _combined(initial_build, initial_evolutions)
    initial_heavy = weapon.type == "melee" and attack.category in HEAVY_CATEGORIES
    initial_build_crit = float(initial_build.proportional.get("crit_chance", 0)) * (2 if initial_heavy else 1)
    initial_crit = max((float(attack.stats.crit_chance) + float(initial_total.base.get("crit_chance", 0))) * (1 + initial_build_crit + float(initial_evolutions.proportional.get("crit_chance", 0))) * family_factor(initial_total, "crit_chance") + float(initial_total.flat.get("crit_chance", 0)), 0)
    initial_status = _scalar(float(attack.stats.status_chance), "status_chance", initial_total)
    initial_crit, initial_status = _derived_chances(initial_crit, initial_status, initial_total)
    initial_ms_bonus = 0 if weapon.type == "melee" or initial_total.proportional.get("multishot_lock") else float(initial_total.proportional.get("multishot", 0))
    initial_multishot = max(float(attack.stats.multishot) * (1 + initial_ms_bonus), 1)
    acquisition = [effect for effect in (*initial_build_effects, *initial_evolution_effects) if effect.stat in {"duplicated_hit", "random_proc"}]
    duplicate_acquisition = _special_value(acquisition, "duplicated_hit")
    random_acquisition = _special_value(acquisition, "random_proc")
    if weapon.type == "melee":
        acquisition_attempts = initial_multishot + duplicate_acquisition * max(0, 1 - abs(initial_crit - 1))
        initial_rate, _ = _melee_rate(weapon, attack, initial_total)
    else:
        acquisition_attempts = initial_multishot
        _, initial_rate, _ = _ranged_rate(weapon, attack, initial_total, initial_multishot)
    initial_duration = _scalar(float(attack.stats.status_duration), "status_duration", initial_total)
    automatic_model = StatusModel(provisional_model.damage, provisional_model.forced_procs, initial_status, acquisition_attempts, initial_rate, initial_duration, random_acquisition)
    build_resolved, build_positions = _resolve_effects(weapon, attack, build_effects, provisional, automatic_model, equipped)
    evolution_resolved, evolution_positions = _resolve_effects(weapon, attack, evolution_effects, provisional, automatic_model, equipped)
    build = aggregate(effect for effect in build_resolved if automatic_value(effect, "on") not in POSITION_EVENTS and effect.stat not in DEFERRED_STATS and not (effect.stat == "crit_damage" and automatic_value(effect, "with") == "puncture_status_chance"))
    evolutions = aggregate(effect for effect in evolution_resolved if automatic_value(effect, "on") not in POSITION_EVENTS and effect.stat not in DEFERRED_STATS)
    total = _combined(build, evolutions)
    base_damage, original = _base_damage(weapon, attack, evolutions)
    damage = _damage(weapon, attack, base_damage, original, build, evolutions)
    heavy = weapon.type == "melee" and attack.category in HEAVY_CATEGORIES
    build_crit = float(build.proportional.get("crit_chance", 0)) * (2 if heavy else 1)
    crit_base = float(attack.stats.crit_chance) + float(total.base.get("crit_chance", 0))
    crit = max(crit_base * (1 + build_crit + float(evolutions.proportional.get("crit_chance", 0))) * family_factor(total, "crit_chance") + float(total.flat.get("crit_chance", 0)), 0)
    status = _scalar(float(attack.stats.status_chance), "status_chance", total)
    crit, status = _derived_chances(crit, status, total)
    if weapon.type == "melee" and attack.category == "slide": crit *= max(1 + float(total.proportional.get("slide_crit_chance", 0)), 0)
    crit_damage = _scalar(float(attack.stats.crit_damage), "crit_damage", total, minimum=1)
    doughty = next((effect for effect in (*build_resolved, *evolution_resolved) if effect.stat == "crit_damage" and automatic_value(effect, "with") == "puncture_status_chance"), None)
    doughty_bonus = 0.0
    if doughty is not None:
        per = float(automatic_value(doughty, "per", 0.1) or 0.1)
        maximum = 50 if doughty.maximum is None else float(doughty.maximum)
        doughty_bonus = true_round(min(damage.weight("puncture") * status / per * float(doughty.value), maximum), 1)
        crit_damage += doughty_bonus
    weakpoint_common = float(total.proportional.get("weakpoint_crit_chance", 0))
    weakpoint_family = sum(float(family.get("weakpoint_crit_chance", 0)) for family in total.families.values())
    weakpoint_crit = 0.0 if weapon.type == "melee" else max(crit + float(attack.stats.crit_chance) * (weakpoint_common + weakpoint_family) + float(total.flat.get("weakpoint_crit_chance", 0)), 0)
    crit_tier_chance = clamp(_special_value((*build_resolved, *evolution_resolved), "crit_tier", "critical_hit"), 0, 1)
    ms_bonus = 0 if weapon.type == "melee" or total.proportional.get("multishot_lock") else float(total.proportional.get("multishot", 0))
    ms_ammo_bonus = _multishot_ammo_bonus(total)
    if attack.delivery == "beam" and ms_ammo_bonus and not total.proportional.get("multishot_lock"): ms_bonus *= 1 + ms_ammo_bonus
    multishot = max(float(attack.stats.multishot) * (1 + ms_bonus), 1)
    if attack.delivery != "beam" and ms_ammo_bonus: damage *= 1 + ms_ammo_bonus * (1 - 1 / multishot)
    if weapon.type == "melee":
        instant_rate, category_stats = _melee_rate(weapon, attack, total)
        fire_rate = instant_rate
        stance = _stance_combo(weapon, attack)
        if stance: damage *= max(float(stance.get("multiplier", 1)), 0)
        if attack.category in SLAM_CATEGORIES: damage *= max(1 + float(total.proportional.get("slam_damage", 0)), 0)
    else:
        instant_rate, fire_rate, category_stats = _ranged_rate(weapon, attack, total, multishot)
    duration = _scalar(float(attack.stats.status_duration), "status_duration", total)
    forced = _forced_procs(attack, (*build_resolved, *evolution_resolved))
    duplicate = clamp(_special_value((*build_resolved, *evolution_resolved), "duplicated_hit"), 0, 1)
    duplicate_multiplier = 1 + duplicate * max(0, 1 - abs(crit - 1)) if weapon.type == "melee" else 1
    status_attempts = multishot + duplicate * max(0, 1 - abs(crit - 1)) if weapon.type == "melee" else multishot
    status_model = StatusModel(damage, forced, status, status_attempts, fire_rate, duration, _special_value((*build_resolved, *evolution_resolved), "random_proc"))
    status_effects = status_model.non_damage_effects()
    faction = _faction_factor(weapon, total)
    non_crit_damage = family_bonus(total, "non_critical_hit", "damage_bonus") + float(total.proportional.get("non_crit_bonus_damage", 0))
    non_crit_chance = max((float(automatic_value(effect, "chance", 0) or 0) for effect in (*build_resolved, *evolution_resolved) if effect.family == "non_critical_hit"), default=0)
    weakpoint_bonus = max(float(total.proportional.get("weakpoint_damage", 0)), 0)
    effective = Stats(damage=damage, forced_procs=forced, crit_chance=crit, weakpoint_crit_chance=weakpoint_crit, crit_damage=crit_damage, status_chance=status, status_duration=duration, status_damage=max(1 + float(total.proportional.get("status_damage", 0)), 1), multishot=multishot, fire_rate=instant_rate, sustained_rate=fire_rate, faction_damage=faction, non_crit_bonus_damage=non_crit_damage, non_crit_bonus_chance=non_crit_chance, weakpoint_damage_bonus=weakpoint_bonus, special_effects=tuple((*build_resolved, *evolution_resolved)), **category_stats)
    for stat in ("projectile_speed", "range", "punch_through", "accuracy", "recoil", "zoom", "ammo_maximum"):
        base_value = float(getattr(attack.stats, stat, 0)) if hasattr(attack.stats, stat) else 0
        effective[stat] = _additive_scalar(base_value, stat, total) if stat == "punch_through" else _scalar(base_value, stat, total)
    projectile_speed = float(effective.projectile_speed)
    range_scale = max(1 + float(total.proportional.get("explosion_radius", 0)), 0) if attack.aoe else 1 + projectile_speed
    effective.start_range = float(attack.stats.falloff.get("start_range", 0)) * range_scale
    effective.end_range = float(attack.stats.falloff.get("end_range", 0)) * range_scale
    final_multiplier = attack.stats.falloff.get("final_multiplier")
    effective.final_multiplier = 1.0 if final_multiplier is None else float(final_multiplier)
    effective.noise_level = total.proportional.get("noise_level", attack.stats.noise_level)
    base = Stats(damage=base_damage, forced_procs=attack.stats.forced_procs, crit_chance=attack.stats.crit_chance, crit_damage=attack.stats.crit_damage, status_chance=attack.stats.status_chance, status_duration=attack.stats.status_duration, multishot=attack.stats.multishot, fire_rate=attack.stats.fire_rate)
    modded = Stats(damage=damage, crit_chance=crit, crit_damage=crit_damage, status_chance=status, status_duration=duration, multishot=multishot, **category_stats)
    body_crit, weak_crit = crit, weakpoint_crit
    if weapon.type == "secondary":
        per_stack, reset = enervate_parameters([*build_resolved, *evolution_resolved])
        body_bonus = average_enervate_bonus(crit, per_stack, reset)
        weak_bonus = average_enervate_bonus(weakpoint_crit, per_stack, reset)
        body_crit += body_bonus
        weak_crit += weak_bonus
    else:
        body_bonus = weak_bonus = 0
    body_tier_bonus = min(body_crit, 1) * crit_tier_chance
    weak_tier_bonus = min(weak_crit, 1) * crit_tier_chance
    falloff_multiplier, damage_mass = _spatial_falloff(attack, effective)
    average = Metrics(crit_chance=body_crit, crit_multiplier=crit_multiplier(body_crit + body_tier_bonus, crit_damage), weakpoint_crit_chance=weak_crit, weakpoint_crit_multiplier=crit_multiplier(weak_crit + weak_tier_bonus, crit_damage), fire_rate=fire_rate, procs_per_shot=status * status_attempts, melee_duplicate_multiplier=duplicate_multiplier, melee_doughty_bonus=doughty_bonus, crit_tier_bonus=body_tier_bonus, weakpoint_crit_tier_bonus=weak_tier_bonus, secondary_enervate_bonus=body_bonus, weakpoint_secondary_enervate_bonus=weak_bonus, falloff_multiplier=falloff_multiplier)
    density = DensityMetrics(damage_mass=damage_mass)
    result = AttackResult(attack.name, attack, base, modded, effective, build, evolutions, average, deepcopy(average), density, status_effects, list(attack.children), original)
    combo_multiplier = 1
    if heavy:
        combo_multiplier = max(1, min(int(weapon.combo.get("max_combo", 12)), int(weapon.runtime.combo)))
    average.combo_multiplier = combo_multiplier
    for zone, fields in ZONE_FIELDS.items():
        direct_total = damage_total(damage, weapon.target, zone=zone, weakpoint_bonus=weakpoint_bonus, status_effects=status_effects)
        if direct_total is None:
            setattr(average, fields[0], None)
            setattr(average, fields[1], None)
            continue
        chance = weak_crit if zone == "weakpoint" else body_crit
        tier_bonus = weak_tier_bonus if zone == "weakpoint" else body_tier_bonus
        direct_hits = 1 if weapon.type == "melee" else multishot
        direct = direct_total * direct_hits * faction * _hit_multiplier(chance, tier_bonus, crit_damage, non_crit_damage, non_crit_chance) * duplicate_multiplier * combo_multiplier
        dot = _dot_value(weapon, result, zone) * combo_multiplier
        _set_zone_damage(average, density, zone, fields, direct, dot)
    refresh_metrics(average)
    _refresh_density(density, average.fire_rate)
    _apply_position_mixture(weapon, result, [*build_positions, *evolution_positions])
    result.final = deepcopy(average)
    return result


def calculate_weapon(weapon: Any) -> dict[str, AttackResult]:
    build_effects = tuple(effect for upgrade in weapon.build for effect in upgrade.resolve_manual())
    evolution_effects = _runtime_evolution_effects(weapon)
    needed: set[str] = set()

    def collect(name: str, path: frozenset[str] = frozenset()) -> None:
        if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
        if name not in weapon.attacks: raise ValueError(f"unknown child attack {name!r}")
        if name in needed: return
        needed.add(name)
        for child in weapon.attacks[name].children: collect(child, path | {name})

    collect(str(weapon.runtime.attack))
    results = {name: _calculate_attack(weapon, weapon.attacks[name], build_effects, evolution_effects) for name in needed}

    def fold_metrics(output: Metrics, own: Metrics, children: list[Metrics]) -> None:
        for fields in ZONE_FIELDS.values():
            direct_values = [getattr(own, fields[0]), *(getattr(child, fields[0]) for child in children)]
            dot_values = [getattr(own, fields[1]), *(getattr(child, fields[1]) for child in children)]
            if not any(value is not None for value in (*direct_values, *dot_values)):
                for field in fields: setattr(output, field, None)
                continue
            direct = sum(float(value or 0) for value in direct_values)
            dot = sum(float(value or 0) for value in dot_values)
            setattr(output, fields[0], direct)
            setattr(output, fields[1], dot)
            setattr(output, fields[2], direct + dot)
            setattr(output, fields[3], direct * own.fire_rate)
            setattr(output, fields[4], dot * own.fire_rate)
            setattr(output, fields[5], (direct + dot) * own.fire_rate)

    def fold(name: str, path: frozenset[str] = frozenset()) -> AttackResult:
        if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
        result = results[name]
        children = [fold(child, path | {name}) for child in result.children]
        fold_metrics(result.final, result.average, [child.final for child in children])
        for density_field in DENSITY_FIELDS.values():
            density_values = [getattr(result.density, density_field), *(getattr(child.density, density_field) for child in children)]
            density = sum(float(value or 0) for value in density_values) if any(value is not None for value in density_values) else None
            setattr(result.density, density_field, density)
            setattr(result.density, f"{density_field}_per_second", None if density is None else density * result.average.fire_rate)
        return result

    fold(str(weapon.runtime.attack))
    return results
