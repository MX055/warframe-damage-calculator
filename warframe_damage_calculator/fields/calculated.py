from ..models.data import Data
from ..models.dist import Dist
from ..utils.types import Number


class CalculatedValues(Data):
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    damage_bonus: Number
    corpus_damage: Number
    grineer_damage: Number
    infested_damage: Number
    orokin_damage: Number
    murmur_damage: Number
    sentient_damage: Number
    crit_chance: Number
    crit_damage: Number
    status_chance: Number
    status_damage: Number
    attack_speed: Number
    melee_duplicate: Number
    melee_doughty: Number
    multishot: Number
    non_crit_bonus_chance: Number
    non_crit_bonus_damage: Number
    fire_rate: Number
    burst_count: int
    burst_delay: Number
    charge_time: Number
    reload_speed: Number
    recharge_rate: Number
    ammo_cost: Number
    ammo_efficiency: Number
    magazine_capacity: Number
    weakpoint_damage: Number
    weakpoint_crit_chance: Number
    internal_bleeding: Number
    hunter_munitions: Number
    primed_chamber: Number
    projectile_speed: Number
    range: Number
    start_range: Number
    end_range: Number
    final_multiplier: Number
    vigilante_bonus: Number
    secondary_enervate: Number
    secondary_encumber: Number


class CalculatedModeStats(CalculatedValues):
    pass


class CalculatedStats(CalculatedValues):
    pass


class ModdedStats(Data):
    additive: CalculatedModeStats = CalculatedModeStats()
    multiplicative: CalculatedModeStats = CalculatedModeStats()
    base: CalculatedModeStats = CalculatedModeStats()
    flat: CalculatedModeStats = CalculatedModeStats()


class AverageStats(Data):
    crit_chance: Number
    crit_multiplier: Number
    weakpoint_crit_chance: Number
    weakpoint_crit_multiplier: Number
    corpus_damage: Number
    grineer_damage: Number
    infested_damage: Number
    orokin_damage: Number
    murmur_damage: Number
    sentient_damage: Number
    fire_rate: Number
    procs_per_shot: Number
    flat_dph: Number
    flat_weakpoint_dph: Number
    flat_dps: Number
    flat_weakpoint_dps: Number
    flat_dotph: Number
    flat_weakpoint_dotph: Number
    flat_dotps: Number
    flat_weakpoint_dotps: Number
    total_dph: Number
    total_weakpoint_dph: Number
    total_dps: Number
    total_weakpoint_dps: Number
    melee_doughty_bonus: Number
    melee_duplicate_multiplier: Number
    primed_chamber_multiplier: Number
    secondary_enervate_bonus: Number
    weakpoint_secondary_enervate_bonus: Number
