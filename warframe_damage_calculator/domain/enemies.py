from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import floor
from typing import Any, Mapping, Self

from .runtime import Runtime


type Scaling = tuple[float, float, float, float]

STANDARD_HEALTH: Scaling = (0.015, 2.0, 10.733, 0.5)
STANDARD_SHIELDS: Scaling = (0.02, 1.75, 2.0, 0.75)
ARMOR_SCALING: Scaling = (0.005, 1.75, 0.4, 0.75)
OVERGUARD_SCALING: Scaling = (0.0015, 4.0, 260.0, 0.9)
HEALTH_BY_FACTION: dict[str, Scaling] = {"grineer": (0.015, 2.12, 10.733, 0.72), "corpus": (0.015, 2.12, 13.416, 0.55), "infested": (0.0225, 2.12, 16.1, 0.72), "orokin": (0.015, 2.1, 10.733, 0.685)}
SHIELDS_BY_FACTION: dict[str, Scaling] = {"grineer": (0.02, 1.75, 1.6, 0.75), "corpus": (0.02, 1.76, 2.0, 0.76), "infested": (0.02, 1.75, 1.6, 0.75)}


def _level_multiplier(delta: float, scaling: Scaling, start: float = 70, end: float = 80) -> float:
    first_coefficient, first_exponent, second_coefficient, second_exponent = scaling
    first = first_coefficient * delta ** first_exponent
    second = second_coefficient * delta ** second_exponent
    if delta < start: transition = 0.0
    elif delta > end: transition = 1.0
    else:
        position = (delta - start) / (end - start)
        transition = 3 * position ** 2 - 2 * position ** 3
    return 1 + first + (second - first) * transition


@dataclass(slots=True)
class EnemyStats:
    health: float = 1
    shields: float = 0
    armor: float = 0
    overguard: float = 0


@dataclass(slots=True)
class BodyPart:
    type: str = "normal"
    multiplier: float = 1
    name: str = "body"


class Enemy:
    __slots__ = ("name", "faction", "base_level", "stats", "bodyparts", "modifiers", "runtime")

    def __init__(self, *, name: str = "Enemy", faction: str = "", base_level: float = 1, stats: EnemyStats | None = None, bodyparts: Mapping[str, BodyPart] | None = None, modifiers: Mapping[str, int | float] | None = None, runtime: Mapping[str, Any] | None = None) -> None:
        self.name = name
        self.faction = faction
        self.base_level = float(base_level)
        self.stats = stats or EnemyStats()
        self.bodyparts = dict(bodyparts or {"body": BodyPart()})
        self.modifiers = {kind.lower(): float(value) for kind, value in (modifiers or {}).items()}
        self.runtime = Runtime({"level", "steel_path", "empowered"}, {"level": 1, "steel_path": False, "empowered": False} | dict(runtime or {}))

    def set(self, **values: Any) -> Self:
        self.runtime.set(**values)
        return self

    @classmethod
    def from_record(cls, record: Mapping[str, Any], *, loaded: bool = False) -> Enemy:
        allowed = {"name", "faction", "base_level", "stats", "bodyparts", "modifiers"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown enemy fields: {', '.join(sorted(unknown))}")
        runtime = {"level": 100, "steel_path": False, "empowered": False} if loaded else None
        return cls(name=str(record.get("name", "Enemy")), faction=str(record.get("faction", "")), base_level=float(record.get("base_level", 1)), stats=EnemyStats(**record.get("stats", {})), bodyparts={name: BodyPart(**({"name": name} | dict(part))) for name, part in record.get("bodyparts", {"body": {}}).items()}, modifiers=record.get("modifiers", {}), runtime=runtime)

    def copy(self) -> Enemy:
        return Enemy(name=self.name, faction=self.faction, base_level=self.base_level, stats=deepcopy(self.stats), bodyparts=deepcopy(self.bodyparts), modifiers=self.modifiers, runtime=self.runtime.as_dict())

    @property
    def effective(self) -> EnemyStats:
        delta = max(float(self.runtime.level) - self.base_level, 0)
        path = 2.5 if self.runtime.steel_path else 1
        empowered = 2.5 if self.runtime.empowered else 1
        health = self.stats.health * _level_multiplier(delta, HEALTH_BY_FACTION.get(self.faction, STANDARD_HEALTH)) * path * empowered
        shields = self.stats.shields * _level_multiplier(delta, SHIELDS_BY_FACTION.get(self.faction, STANDARD_SHIELDS)) * path * empowered
        armor = min(floor(self.stats.armor * _level_multiplier(delta, ARMOR_SCALING) * path), 2700)
        overguard = self.stats.overguard * _level_multiplier(delta, OVERGUARD_SCALING, 45, 50)
        return EnemyStats(round(health, 2), round(shields, 2), armor, round(overguard, 2))
