from collections.abc import Mapping

from ..core.data import Data
from ..utils.types import JsonValue, Number


class EvolutionStats(Data):
    ammo_efficiency: JsonValue
    attack_speed: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    crit_from_status: JsonValue
    damage: JsonValue
    damage_bonus: JsonValue
    fire_rate: JsonValue
    heavy_attack_speed: JsonValue
    initial_combo: JsonValue
    magazine_capacity: JsonValue
    multishot: JsonValue
    non_crit_bonus_chance: JsonValue
    non_crit_bonus_damage: JsonValue
    projectile_speed: JsonValue
    range: JsonValue
    reload_speed: JsonValue
    slam_damage: JsonValue
    slide_crit_chance: JsonValue
    status_chance: JsonValue
    status_duration: JsonValue
    status_from_crit: JsonValue
    weakpoint_damage: JsonValue


class EvolutionPerk(Data):
    description: str = ""
    stats: EvolutionStats = {}


class EvolutionTier(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, EvolutionPerk):
            value = EvolutionPerk(value)
        super().__setitem__(key, value)


class Evolutions(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, EvolutionTier):
            value = EvolutionTier(value)
        super().__setitem__(key, value)


class ConversionBonus(Data):
    value: Number = 0.0
    max: Number = 0.0


class ResolvedEvolutionModeStats(Data):
    ammo_efficiency: Number = 0.0
    attack_speed: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 0.0
    crit_from_status: ConversionBonus = ConversionBonus()
    damage: Number = 0.0
    damage_bonus: Number = 0.0
    fire_rate: Number = 0.0
    heavy_attack_speed: Number = 0.0
    initial_combo: Number = 0.0
    magazine_capacity: Number = 0.0
    multishot: Number = 0.0
    non_crit_bonus_chance: Number = 0.0
    non_crit_bonus_damage: Number = 0.0
    projectile_speed: Number = 0.0
    range: Number = 0.0
    reload_speed: Number = 0.0
    slam_damage: Number = 0.0
    slide_crit_chance: Number = 0.0
    status_chance: Number = 0.0
    status_duration: Number = 0.0
    status_from_crit: ConversionBonus = ConversionBonus()
    weakpoint_damage: Number = 0.0


class ResolvedEvolutionStat(Data):
    additive: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    multiplicative: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    base: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    flat: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
