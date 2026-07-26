from ..core.data import Data
from ..core.dist import Dist
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
    status_duration: Number
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
    ammo_maximum: Number
    weakpoint_damage: Number
    weakpoint_crit_chance: Number
    projectile_speed: Number
    range: Number
    start_range: Number
    end_range: Number
    final_multiplier: Number
    heavy_attack_speed: Number
    heavy_attack_efficiency: Number
    initial_combo: Number
    slam_damage: Number
    slide_crit_chance: Number
    punch_through: Number
    zoom: Number
    noise_level: str
    accuracy: Number
    recoil: Number


class CalculatedModeStats(CalculatedValues):
    pass


class CalculatedStats(CalculatedValues):
    pass


class CalculatedMultiplicativeFamilies(Data):
    pass


class StatusEffects(Data):
    viral: Number = 0.0
    magnetic: Number = 0.0
    corrosive: Number = 0.0
    heat: Number = 0.0


class ModdedStats(Data):
    proportional: CalculatedModeStats = CalculatedModeStats()
    base: CalculatedModeStats = CalculatedModeStats()
    flat: CalculatedModeStats = CalculatedModeStats()
    # Runtime product-family bonuses (e.g. melee CO), folded with build/evo families.
    multiplicative_families: CalculatedMultiplicativeFamilies = CalculatedMultiplicativeFamilies()


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
    flat_resistant_dph: Number
    flat_dps: Number
    flat_weakpoint_dps: Number
    flat_resistant_dps: Number
    flat_dotph: Number
    flat_weakpoint_dotph: Number
    flat_resistant_dotph: Number
    flat_dotps: Number
    flat_weakpoint_dotps: Number
    flat_resistant_dotps: Number
    total_dph: Number
    total_weakpoint_dph: Number
    total_resistant_dph: Number
    total_dps: Number
    total_weakpoint_dps: Number
    total_resistant_dps: Number
    melee_doughty_bonus: Number
    melee_duplicate_multiplier: Number
    combo_multiplier: Number
    first_shot_damage_multiplier: Number = 1.0
    secondary_enervate_bonus: Number
    weakpoint_secondary_enervate_bonus: Number
