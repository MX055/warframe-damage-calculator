from __future__ import annotations

from math import sqrt
from typing import Literal

from ..domain.damage import Dist
from ..domain.enemies import Enemy


type HitZone = Literal["normal", "weakpoint", "resistant"]



def status_vulnerability(stacks: float) -> float:
    stacks = max(min(stacks, 10), 0)
    return 1 + min(stacks, 1) + 0.25 * max(stacks - 1, 0)


def armor_damage_taken(armor: float) -> float:
    return 1 - 0.9 * sqrt(max(min(armor, 2700), 0) / 2700)


def remaining_armor(statuses: dict[str, float]) -> float:
    corrosive = max(min(statuses.get("corrosive", 0), 10), 0)
    corrosive_strip = 0.26 * min(corrosive, 1) + 0.06 * max(corrosive - 1, 0)
    heat_strip = 0.5 * max(min(statuses.get("heat", 0), 1), 0)
    direct_strip = max(min(statuses.get("armor_reduction", 0), 1), 0)
    return (1 - corrosive_strip) * (1 - heat_strip) * (1 - direct_strip)


def bodypart_multiplier(enemy: Enemy | None, zone: HitZone, weakpoint_bonus: float = 0) -> float | None:
    if enemy is None: return 1.0 if zone == "normal" else None
    values = [float(part.multiplier) for part in enemy.bodyparts.values() if part.type == zone]
    if not values: return None
    multiplier = sum(values) / len(values)
    return multiplier * (1 + weakpoint_bonus) if zone == "weakpoint" else multiplier


def defense_multiplier(enemy: Enemy | None, kind: str, *, dot: bool, statuses: dict[str, float], overguard_multiplier: float = 1) -> float:
    if enemy is None: return 1.0
    effective = enemy.effective
    health, shields, overguard = float(effective.health), float(effective.shields), float(effective.overguard)
    total = health + shields + overguard
    if total <= 0: return 1.0
    armor_taken = armor_damage_taken(float(effective.armor) * remaining_armor(statuses))
    viral_taken = status_vulnerability(statuses.get("viral", 0))
    magnetic_taken = status_vulnerability(statuses.get("magnetic", 0))
    if kind == "true":
        health_share, shield_share, health_taken = health + shields, 0.0, viral_taken
    elif kind == "toxin":
        health_share, shield_share, health_taken = health + shields, 0.0, armor_taken * viral_taken
    else:
        health_share, shield_share = health, shields
        health_taken = (1.0 if dot and kind == "slash" else armor_taken) * viral_taken
    shield_taken = 0.5 * magnetic_taken
    overguard_taken = 0.0 if dot else (1.5 if kind == "void" else 1.0) * magnetic_taken * overguard_multiplier
    return (health_share * health_taken + shield_share * shield_taken + overguard * overguard_taken) / total


def damage_multiplier(enemy: Enemy | None, kind: str, *, zone: HitZone, dot: bool = False, weakpoint_bonus: float = 0, status_effects: dict[str, float] | None = None, overguard_multiplier: float = 1) -> float | None:
    part = bodypart_multiplier(enemy, zone, weakpoint_bonus)
    if part is None: return None
    modifier = 1.0 if enemy is None else float(enemy.modifiers.get(kind, 1))
    return modifier * defense_multiplier(enemy, kind, dot=dot, statuses=status_effects or {}, overguard_multiplier=overguard_multiplier) * part


def damage_total(damage: Dist, enemy: Enemy | None, *, zone: HitZone, dot: bool = False, weakpoint_bonus: float = 0, status_effects: dict[str, float] | None = None, overguard_multiplier: float = 1) -> float | None:
    if bodypart_multiplier(enemy, zone, weakpoint_bonus) is None: return None
    return sum(amount * float(damage_multiplier(enemy, kind, zone=zone, dot=dot, weakpoint_bonus=weakpoint_bonus, status_effects=status_effects, overguard_multiplier=overguard_multiplier) or 0) for kind, amount in damage.items())
