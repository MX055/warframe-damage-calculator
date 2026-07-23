from math import expm1, log1p
from typing import Any

from ..fields.attack_result import AttackResult
from ..fields.calculated import AverageStats
from ..utils.constants import DOT_MULTIPLIERS
from ..utils.types import Number
from ..models.upgrade import Upgrade


def crit_multiplier(crit_chance: Number, crit_damage: Number) -> float:
    return 1 + crit_chance * (crit_damage - 1)


def refresh_dps_from_dph(average: AverageStats) -> None:
    average.flat_dps = average.fire_rate * average.flat_dph
    average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
    average.total_dph = average.flat_dph + average.flat_dotph
    average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
    average.total_dps = average.flat_dps + average.flat_dotps
    average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps


def status_hits(result: AttackResult) -> float:
    build, stats, modded = result.build, result.attack.stats, result.modded
    hits = max(modded.get("multishot", stats.multishot), 1)
    duplicate = modded.get("melee_duplicate", 0)
    chance = max(stats.crit_chance * (1 + build.crit_chance) * modded.multiplicative_crit_chance + modded.flat_crit_chance, 0)
    return hits + duplicate * max(0, 1 - abs(chance - 1))


def effective_attacks_per_second(weapon: Any, result: AttackResult) -> float:
    stats, base, modded = result.attack.stats, result.base, result.modded
    if "attack_speed" in modded:
        return max(stats.fire_rate * modded.attack_speed / (base.attack_speed or 1), 0)
    if "magazine_capacity" not in modded:
        return max(stats.fire_rate, 0)

    build = result.build
    speed = 1 if build.fire_rate_lock else max(1 + build.fire_rate, 0.01)
    fire_rate = max(stats.fire_rate * speed, 0.05) * modded.multiplicative_fire_rate
    burst_count = max(stats.burst_count, 1)
    ammo_cost = max(float(modded.get("ammo_cost", stats.ammo_cost)), 0)
    if ammo_cost <= 0:
        return fire_rate
    shots = modded.magazine_capacity / ammo_cost
    bursts = shots / burst_count
    is_battery = "recharge_delay" in weapon.data.ammo
    reload_speed = modded.reload_speed + (0 if not is_battery else float("inf") if modded.recharge_rate <= 0 else modded.magazine_capacity / modded.recharge_rate)
    ammo_spent = 1 - modded.ammo_efficiency
    cycle = bursts * (max(stats.charge_time, 0) / speed / modded.multiplicative_fire_rate + (burst_count - 1) * max(stats.burst_delay, 0) / max(speed, 1))
    cycle += (bursts - ammo_spent) / fire_rate + ammo_spent * reload_speed
    return float("inf") if cycle <= 0 else shots / cycle


def average_condition_overload_bonus(weapon: Any, result: AttackResult, time: Number = 5) -> float:
    build, stats = result.build, result.attack.stats
    damage = stats.damage.apply(build.damage).combine().sorted()
    guaranteed, fractional = divmod(max(stats.status_chance * (1 + build.status_chance), 0), 1)
    guaranteed_hits, fractional_hit = divmod(max(status_hits(result), 0), 1)
    probabilities: dict[str, float] = {}
    for damage_type in damage.data:
        weight = damage.weight(damage_type)
        miss = (1 - weight) ** guaranteed * (1 - fractional * weight)
        probabilities[damage_type] = 1 - miss ** guaranteed_hits * (1 - fractional_hit + fractional_hit * miss)
    probabilities.update({damage_type: 1.0 for damage_type, count in stats.forced_procs if count > 0})

    condition_overload = build.condition_overload
    maximum = len(probabilities) if condition_overload.max_stacks == "inf" else int(condition_overload.max_stacks)
    attack_rate = effective_attacks_per_second(weapon, result)
    if maximum <= 0 or attack_rate <= 0:
        return 0.0
    attempts, distribution = attack_rate * time, [1.0] + [0.0] * maximum
    for probability in probabilities.values():
        acquired = 0 if probability <= 0 else 1 if probability >= 1 else -expm1(attempts * log1p(-probability))
        updated = [0.0] * (maximum + 1)
        for count, chance in enumerate(distribution):
            updated[count] += chance * (1 - acquired)
            updated[min(count + 1, maximum)] += chance * acquired
        distribution = updated
    expected = sum(count * chance for count, chance in enumerate(distribution))
    return float(condition_overload.value) * stats.co_factor * expected


def flat_dotph(result: AttackResult, *, weakpoint: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number = 1) -> float:
    base, effective, average = result.base, result.effective, result.average
    if effective.damage.total_damage() <= 0:
        return 0.0
    multiplier = average.weakpoint_crit_multiplier if weakpoint else average.crit_multiplier
    regular = sum(factor * effective.damage.get(damage_type) * effective.damage.weight(damage_type) for damage_type, factor in DOT_MULTIPLIERS) * effective.status_chance
    forced = sum(factor * base.forced_procs.get(damage_type) * effective.damage.get(damage_type) for damage_type, factor in DOT_MULTIPLIERS)
    shot_hits = effective.get("multishot", status_hits(result)) if hits is None else hits
    return (regular + forced) * effective.status_damage * faction_damage ** 2 * multiplier * damage_multiplier * shot_hits + extra_damage


def primary_flat_dotph(result: AttackResult, *, weakpoint: bool = False, faction_damage: Number = 1) -> float:
    damage, forced_procs = result.effective.damage, result.base.forced_procs
    effective, average = result.effective, result.average
    if damage.total_damage() <= 0:
        return 0.0
    crit_chance = average.weakpoint_crit_chance if weakpoint else average.crit_chance
    multiplier = average.weakpoint_crit_multiplier if weakpoint else average.crit_multiplier
    primed = 1 + effective.primed_chamber / effective.magazine_capacity
    hunter_procs = effective.hunter_munitions * min(crit_chance, 1)
    hunter_dpp = 2.1 * damage.total_damage() * max(effective.crit_damage, multiplier) * effective.status_damage * faction_damage ** 2 * primed
    hunter_damage = hunter_procs * hunter_dpp
    impact_ib = (damage.weight("impact") + forced_procs.get("impact")) * effective.internal_bleeding
    guaranteed_proc, fractional_proc = divmod(effective.status_chance, 1)
    ib_procs = impact_ib * effective.status_chance
    ib_dpp = 2.1 * damage.total_damage() * multiplier * effective.status_damage * faction_damage ** 2 * primed
    ib_damage = ib_procs * ib_dpp
    ib_probability = 1 - (1 - impact_ib) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_ib))
    overlap = hunter_procs * ib_probability * min(hunter_dpp, ib_dpp)
    extra = hunter_damage + ib_damage - overlap
    return flat_dotph(result, weakpoint=weakpoint, damage_multiplier=primed, extra_damage=extra * effective.multishot, faction_damage=faction_damage)


def secondary_flat_dotph(result: AttackResult, *, weakpoint: bool = False, faction_damage: Number = 1) -> float:
    # Secondary Encumber calculations need testing in-game
    damage, forced_procs = result.effective.damage, result.base.forced_procs
    effective, average = result.effective, result.average
    if damage.total_damage() <= 0:
        return 0.0
    multiplier = average.weakpoint_crit_multiplier if weakpoint else average.crit_multiplier
    encumber_chance = 1 - (1 - effective.secondary_encumber * min(effective.status_chance, 1)) ** effective.multishot
    encumber_dot = encumber_chance * damage.total_damage() * 14.1 / 13 * multiplier * effective.status_damage * faction_damage ** 2
    ib_procs = ((damage.weight("impact") + forced_procs.get("impact")) * effective.status_chance + encumber_chance / 13) * effective.internal_bleeding
    ib_dpp = 2.1 * damage.total_damage() * multiplier * effective.status_damage * faction_damage ** 2
    extra = ib_procs * ib_dpp * effective.multishot
    return flat_dotph(result, weakpoint=weakpoint, extra_damage=extra + encumber_dot, faction_damage=faction_damage)


def selected_evolution_upgrades(weapon: Any) -> list:
    return [Upgrade({"name": f"evolution {tier} perk {perk}",  "type": "evolution",  "stats": weapon.data.evolutions[str(tier)][str(perk)].get("stats", {})}) for tier, perk in weapon._evolutions.items()]
