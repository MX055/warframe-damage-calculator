from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...domain.damage import Dist
from ...domain.status import StatusModel
from ...domain.upgrades import ResolvedEffect


class Stats(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try: return self[name]
        except KeyError: raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class BaseAttackStats(Stats):
    damage: Dist
    forced_procs: Dist
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float


class ModdedAttackStats(Stats):
    damage: Dist
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float


class EffectiveAttackStats(ModdedAttackStats):
    dot_base_damage: float
    dot_elemental_bonuses: Stats
    forced_procs: Dist
    status_model: StatusModel
    attack_event_rate: float
    reload_time: float
    faction_damage: float
    target_vulnerability: float
    overguard_damage_multiplier: float
    non_crit_bonus_damage: float
    non_crit_bonus_chance: float
    weakpoint_damage_bonus: float
    special_effects: tuple[ResolvedEffect, ...]
    trigger_crit_chance: float


@dataclass(slots=True)
class ResolvedStats:
    proportional: Stats = field(default_factory=Stats)
    multiplicative: Stats = field(default_factory=Stats)
    base: Stats = field(default_factory=Stats)
    flat: Stats = field(default_factory=Stats)
    families: dict[str, Stats] = field(default_factory=dict)
    maximums: dict[str, float] = field(default_factory=dict)
