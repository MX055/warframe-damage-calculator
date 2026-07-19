from collections.abc import Mapping

from ..utils.types import JsonValue, Number
from .data import Data
from .dist import Dist


# ========================================================================
# Weapons
# ========================================================================

# ------------------------------------------------------------------------
# Input Stats
# ------------------------------------------------------------------------

class WeaponStats(Data):
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    crit_chance: Number = 0.0
    crit_damage: Number = 1.0
    status_chance: Number = 0.0


class RangedStats(WeaponStats):
    explosion_damage: Dist = Dist()
    explosion_forced_procs: Dist = Dist()
    burst_count: int = 1
    burst_delay: Number = 0.0
    charge_time: Number = 0.0
    fire_rate: Number = 0.05
    magazine_capacity: Number = 1
    multishot: Number = 1.0
    recharge_rate: Number = 0.0
    reload_speed: Number = 0.0
    weakpoint_damage: Number = 3.0


class MeleeStats(WeaponStats):
    attack_speed: Number = 1.0


class PrimaryStats(RangedStats):
    pass


class SecondaryStats(RangedStats):
    pass

# ------------------------------------------------------------------------
# Context
# ------------------------------------------------------------------------

class WeaponContext(Data):
    category: str = "Weapon"
    type: str | None = None
    name: str | None = None


class RangedContext(WeaponContext):
    category: str = "Ranged"
    trigger: str | None = None
    is_beam: bool = False
    is_battery: bool = False


class PrimaryContext(RangedContext):
    category: str = "Primary"


class SecondaryContext(RangedContext):
    category: str = "Secondary"


class MeleeContext(WeaponContext):
    category: str = "Melee"

# ------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------

class WeaponData(Data):
    stats: WeaponStats = {}
    context: WeaponContext = {}


class RangedData(WeaponData):
    stats: RangedStats
    context: RangedContext


class MeleeData(WeaponData):
    stats: MeleeStats
    context: MeleeContext


class PrimaryData(RangedData):
    stats: PrimaryStats
    context: PrimaryContext


class SecondaryData(RangedData):
    stats: SecondaryStats
    context: SecondaryContext

# ------------------------------------------------------------------------
# Output Satats
# ------------------------------------------------------------------------

class CalculatedStats(Data):
    damage: Dist
    forced_procs: Dist
    explosion_damage: Dist
    explosion_forced_procs: Dist
    multiplicative_base_damage: Number
    base_damage: Number
    faction_damage: Number
    flat_crit_chance: Number
    multiplicative_crit_chance: Number
    crit_chance: Number
    flat_crit_damage: Number
    crit_damage: Number
    status_chance: Number
    status_damage: Number
    attack_speed: Number
    melee_duplicate: Number
    melee_doughty: Number
    multishot: Number
    fire_rate: Number
    multiplicative_fire_rate: Number
    burst_count: int
    burst_delay: Number
    charge_time: Number
    reload_speed: Number
    recharge_rate: Number
    ammo_efficiency: Number
    magazine_capacity: Number
    weakpoint_damage: Number
    multiplicative_weakpoint_crit_chance: Number
    weakpoint_crit_chance: Number
    internal_bleeding: Number
    hunter_munitions: Number
    primed_chamber: Number
    vigilante_bonus: Number
    secondary_enervate: Number
    secondary_encumber: Number


class AverageStats(Data):
    crit_chance: Number
    crit_multiplier: Number
    weakpoint_crit_chance: Number
    weakpoint_crit_multiplier: Number
    fire_rate: Number
    procs_per_shot: Number
    beam_dot_multiplier: Number
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

# ========================================================================
# Upgrades, Builds & Setups
# ========================================================================

# ------------------------------------------------------------------------
# Input Stats
# ------------------------------------------------------------------------

class UpgradeStats(Data):
    ammo_efficiency: JsonValue
    attack_speed: JsonValue
    base_damage: JsonValue
    cold: JsonValue
    corrosive: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    damage: JsonValue
    electricity: JsonValue
    elements: JsonValue
    faction_damage: JsonValue
    fire_rate: JsonValue
    fire_rate_lock: JsonValue
    flat_crit_chance: JsonValue
    flat_crit_damage: JsonValue
    gas: JsonValue
    heat: JsonValue
    hunter_munitions: JsonValue
    impact: JsonValue
    internal_bleeding: JsonValue
    magazine_capacity: JsonValue
    magnetic: JsonValue
    melee_doughty: JsonValue
    melee_duplicate: JsonValue
    multiplicative_base_damage: JsonValue
    multiplicative_crit_chance: JsonValue
    multiplicative_fire_rate: JsonValue
    multiplicative_weakpoint_crit_chance: JsonValue
    multishot: JsonValue
    multishot_lock: JsonValue
    primed_chamber: JsonValue
    puncture: JsonValue
    radiation: JsonValue
    reload_speed: JsonValue
    secondary_encumber: JsonValue
    secondary_enervate: JsonValue
    slash: JsonValue
    status_chance: JsonValue
    status_damage: JsonValue
    toxin: JsonValue
    vigilante_bonus: JsonValue
    viral: JsonValue
    weakpoint_crit_chance: JsonValue
    weakpoint_damage: JsonValue

# ------------------------------------------------------------------------
# Context
# ------------------------------------------------------------------------

class UpgradeContext(Data):
    category: str = "Upgrade"
    type: str | None = None
    name: str | None = None
    compatibility: list[str] = []
    incompatibility: list[str] = []
    requirements: Mapping[str, JsonValue] = {}
    max_rank: int | None = None
    max_stacks: int | None = None
    rank: int | None = None
    stacks: int | None = None
    is_exilus: bool = False
    weapon: str | None = None


class BuildContext(Data):
    sacrificial_set: bool = False


class SetupContext(Data):
    weapon: WeaponContext = {}
    build: BuildContext = {}
    upgrade: UpgradeContext = {}

# ------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------

class UpgradeData(Data):
    stats: UpgradeStats = {}
    context: UpgradeContext = {}


class BuildData(Data):
    upgrades: list[UpgradeData]
    context: BuildContext = {}

# ------------------------------------------------------------------------
# Output Stats
# ------------------------------------------------------------------------

class ResolvedStat(Data):
    damage: Dist = Dist()
    elements: Data = Data()
    ammo_efficiency: Number = 0.0
    attack_speed: Number = 0.0
    base_damage: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 0.0
    faction_damage: Number = 0.0
    fire_rate: Number = 0.0
    fire_rate_lock: bool = False
    flat_crit_chance: Number = 0.0
    flat_crit_damage: Number = 0.0
    hunter_munitions: Number = 0.0
    internal_bleeding: Number = 0.0
    magazine_capacity: Number = 0.0
    melee_doughty: Number = 0.0
    melee_duplicate: Number = 0.0
    multiplicative_base_damage: Number = 0.0
    multiplicative_crit_chance: Number = 0.0
    multiplicative_fire_rate: Number = 0.0
    multiplicative_weakpoint_crit_chance: Number = 0.0
    multishot: Number = 0.0
    multishot_lock: bool = False
    primed_chamber: Number = 0.0
    reload_speed: Number = 0.0
    secondary_encumber: Number = 0.0
    secondary_enervate: Number = 0.0
    status_chance: Number = 0.0
    status_damage: Number = 0.0
    vigilante_bonus: Number = 0.0
    weakpoint_crit_chance: Number = 0.0
    weakpoint_damage: Number = 0.0
