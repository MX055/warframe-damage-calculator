from __future__ import annotations
from dataclasses import dataclass, field, fields
from .dist import dist

@dataclass
class upgrade:
    damage_dist: dist = field(default_factory=dist)
    multiplicative_base_damage: float = 0.0
    base_damage: float = 0.0
    faction_damage: float = 0.0
    weakpoint_damage: float = 0.0
    attack_speed: float = 0.0
    multiplicative_fire_rate: float = 0.0
    fire_rate: float = 0.0
    reload_speed: float = 0.0
    magazine_capacity: float = 0.0
    multishot: float = 0.0
    flat_crit_chance: float = 0.0
    multiplicative_crit_chance: float = 0.0
    crit_chance: float = 0.0
    multiplicative_weakpoint_crit_chance: float = 0.0
    weakpoint_crit_chance: float = 0.0
    flat_crit_damage: float = 0.0
    crit_damage: float = 0.0
    status_chance: float = 0.0
    status_damage: float = 0.0
    hunter_munitions: float = 0.0
    internal_bleeding: float = 0.0
    primed_chamber: float = 0.0
    vigilante_bonus: float = 0.0
    melee_duplicate: float = 0.0

    def __add__(self, other: upgrade) -> upgrade:
        return upgrade(**{field.name: getattr(self, field.name) + getattr(other, field.name) for field in fields(self)})
    
    def __radd__(self, other: int | float) -> upgrade:
        if other == 0: return self
        else: return NotImplemented