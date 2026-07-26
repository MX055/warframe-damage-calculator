from collections.abc import Mapping

from ..core.data import Data
from ..core.dist import Dist
from ..utils.types import JsonValue, Number


class EvolutionStats(Data):
    accuracy: JsonValue
    ammo_efficiency: JsonValue
    ammo_maximum: JsonValue
    attack_speed: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    crit_from_status: JsonValue
    damage: JsonValue
    damage_types: JsonValue
    forced_procs: JsonValue
    damage_bonus: JsonValue
    fire_rate: JsonValue
    heavy_attack_efficiency: JsonValue
    heavy_attack_speed: JsonValue
    impact_to_puncture_conversion: JsonValue
    initial_combo: JsonValue
    magazine_capacity: JsonValue
    multishot: JsonValue
    noise_level: JsonValue
    projectile_speed: JsonValue
    punch_through: JsonValue
    range: JsonValue
    recoil: JsonValue
    reload_speed: JsonValue
    slam_damage: JsonValue
    slide_crit_chance: JsonValue
    status_chance: JsonValue
    status_duration: JsonValue
    status_from_crit: JsonValue
    weakpoint_damage: JsonValue
    zoom: JsonValue


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
    accuracy: Number = 0.0
    ammo_efficiency: Number = 0.0
    ammo_maximum: Number = 0.0
    attack_speed: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 0.0
    crit_from_status: ConversionBonus = ConversionBonus()
    damage: Number = 0.0
    damage_types: Dist = Dist()
    forced_procs: Dist = Dist()
    damage_bonus: Number = 0.0
    fire_rate: Number = 0.0
    heavy_attack_efficiency: Number = 0.0
    heavy_attack_speed: Number = 0.0
    impact_to_puncture_conversion: Number = 0.0
    initial_combo: Number = 0.0
    magazine_capacity: Number = 0.0
    multishot: Number = 0.0
    noise_level: str | None = None
    non_crit_bonus_chance: Number = 0.0
    non_crit_bonus_damage: Number = 0.0
    projectile_speed: Number = 0.0
    punch_through: Number = 0.0
    range: Number = 0.0
    recoil: Number = 0.0
    reload_speed: Number = 0.0
    slam_damage: Number = 0.0
    slide_crit_chance: Number = 0.0
    status_chance: Number = 0.0
    status_duration: Number = 0.0
    status_from_crit: ConversionBonus = ConversionBonus()
    weakpoint_damage: Number = 0.0
    zoom: Number = 0.0


class ResolvedEvolutionMultiplicativeFamilies(Data):
    pass


class ResolvedEvolutionStat(Data):
    proportional: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    base: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    flat: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    multiplicative_families: ResolvedEvolutionMultiplicativeFamilies = ResolvedEvolutionMultiplicativeFamilies()
    magazine_position: list = []
    stacking_reset: list = []
    application_chance: list = []
    conversions: list = []
