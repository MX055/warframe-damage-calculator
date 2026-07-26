from __future__ import annotations

from math import sqrt
from typing import Any, Literal

from ..core.dist import Dist
from ..fields.calculated import AverageStats, StatusEffects
from ..utils.types import DamageType


type HitZone = Literal["normal", "weakpoint", "resistant"]
FACTION_STATS = {
    "Corpus": "corpus_damage",
    "Corpus Amalgam": "corpus_damage",
    "Grineer": "grineer_damage",
    "Kuva Grineer": "grineer_damage",
    "Infestation": "infested_damage",
    "Infested": "infested_damage",
    "Infested Deimos": "infested_damage",
    "Orokin": "orokin_damage",
    "The Murmur": "murmur_damage",
    "Sentient": "sentient_damage",
}


def fingerprint(target: Any | None) -> object:
    return None if target is None else (id(target), repr(target.data))


def faction_damage(average: AverageStats, target: Any | None) -> float:
    if target is None: return max(float(average.corpus_damage), float(average.grineer_damage), float(average.infested_damage), float(average.orokin_damage), float(average.murmur_damage), float(average.sentient_damage))
    stat = FACTION_STATS.get(str(target.data.faction))
    return float(average.get(stat, 1) if stat else 1)


def armor_damage_taken(armor: float) -> float:
    return 1 - 0.9 * sqrt(max(min(armor, 2700), 0) / 2700)


def status_vulnerability(stacks: float) -> float:
    stacks = max(min(stacks, 10), 0)
    return 1 + min(stacks, 1) + 0.25 * max(stacks - 1, 0)


def corrosive_armor_strip(stacks: float) -> float:
    stacks = max(min(stacks, 10), 0)
    return 0.26 * min(stacks, 1) + 0.06 * max(stacks - 1, 0)


def remaining_armor_multiplier(status_effects: StatusEffects | None) -> float:
    if status_effects is None: return 1.0
    corrosive_remaining = 1 - corrosive_armor_strip(float(status_effects.corrosive))
    heat_remaining = 1 - 0.5 * max(min(float(status_effects.heat), 1), 0)
    return corrosive_remaining * heat_remaining


def bodypart_average(target: Any | None, zone: HitZone) -> float:
    if target is None: return 1.0
    values = [float(part.multiplier) for part in target.data.bodyparts.values() if part.type == zone]
    return sum(values) / len(values) if values else 0.0


def bodypart_multiplier(target: Any | None, zone: HitZone, *, weakpoint_bonus: float = 0) -> float:
    multiplier = bodypart_average(target, zone)
    return multiplier * (1 + weakpoint_bonus) if zone == "weakpoint" else multiplier


def defense_multiplier(target: Any | None, damage_type: DamageType, *, dot: bool = False, status_effects: StatusEffects | None = None) -> float:
    if target is None: return 1.0
    stats = target.results.effective
    health, shields, overguard = float(stats.health), float(stats.shields), float(stats.overguard)
    total = health + shields + overguard
    armor_taken = armor_damage_taken(float(stats.armor) * remaining_armor_multiplier(status_effects))
    viral_taken = status_vulnerability(float(status_effects.viral)) if status_effects is not None else 1.0
    magnetic_taken = status_vulnerability(float(status_effects.magnetic)) if status_effects is not None else 1.0
    if damage_type == "true":
        health_share = health + shields
        shield_share = 0.0
        health_taken = viral_taken
    elif damage_type == "toxin":
        health_share = health + shields
        shield_share = 0.0
        health_taken = armor_taken * viral_taken
    else:
        health_share = health
        shield_share = shields
        health_taken = (1.0 if dot and damage_type == "slash" else armor_taken) * viral_taken
    shield_taken = 0.5 * magnetic_taken
    overguard_taken = 0.0 if dot else (1.5 if damage_type == "void" else 1.0) * magnetic_taken
    return (health_share * health_taken + shield_share * shield_taken + overguard * overguard_taken) / total


def damage_type_multiplier(target: Any | None, damage_type: DamageType, *, dot: bool = False, status_effects: StatusEffects | None = None, zone: HitZone = "normal", weakpoint_bonus: float = 0) -> float:
    if target is None: return 1.0
    modifier = float(target.data.modifiers.get(damage_type, 1))
    return modifier * defense_multiplier(target, damage_type, dot=dot, status_effects=status_effects) * bodypart_multiplier(target, zone, weakpoint_bonus=weakpoint_bonus)


def damage_total(damage: Dist, target: Any | None, *, status_effects: StatusEffects | None = None, zone: HitZone = "normal", weakpoint_bonus: float = 0) -> float:
    if target is None: return float(damage.total_damage())
    return sum(float(value) * damage_type_multiplier(target, damage_type, status_effects=status_effects, zone=zone, weakpoint_bonus=weakpoint_bonus) for damage_type, value in damage)
