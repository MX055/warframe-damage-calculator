from collections.abc import Mapping

from ..utils.types import DamageType, JsonValue, Number
from .data import Data
from .dist import Dist


class DistData(Data):
    impact: Number
    puncture: Number
    slash: Number
    blast: Number
    corrosive: Number
    gas: Number
    magnetic: Number
    radiation: Number
    viral: Number
    cold: Number
    electricity: Number
    heat: Number
    toxin: Number
    void: Number
    tau: Number
    true: Number


# ========================================================================
# Weapons
# ========================================================================

# ------------------------------------------------------------------------
# Input Stats
# ------------------------------------------------------------------------

class GlobalWeaponStats(Data):
    reload_time: Number = 0.0
    magazine_size: Number = 1
    recharge_rate: Number = 0.0
    incarnon_charges: Number = 0
    incarnon_recharge_count: Number = 0
    disposition: Number = 0.0
    is_incarnon: bool = False
    is_progenitor: bool = False
    is_beam: bool = False
    is_battery: bool = False


class AttackStats(Data):
    ammo_cost: Number = 1
    punch_through: Number | str = 0.0
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    falloff: Mapping[str, JsonValue] = {}
    crit_chance: Number = 0.0
    crit_damage: Number = 1.0
    status_chance: Number = 0.0
    multishot: Number = 1.0
    fire_rate: Number = 0.05
    burst_count: int = 1
    burst_delay: Number = 0.0
    charge_time: Number = 0.0
    co_factor: Number = 1.0
    co_effect: str = "adds"

class WeaponStats(Data):
    ammo_cost: Number = 1
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    punch_through: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 1.0
    status_chance: Number = 0.0


class RangedStats(WeaponStats):
    burst_count: int = 1
    burst_delay: Number = 0.0
    charge_time: Number = 0.0
    fire_rate: Number = 0.05
    falloff: Mapping[str, JsonValue] = {}
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
    type: str | None = None
    name: str | None = None
    subtype: str | None = None


class AttackContext(Data):
    name: str | None = None
    child: str | list[str] | None = None
    trigger: str | None = None
    projectile: str | None = None


class Attack(Data):
    trigger: str | None = None
    delivery: str | None = None
    aoe: bool = False
    children: list[str] = []
    stats: AttackStats = {}


class Attacks(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, Attack):
            value = Attack(value)
        super().__setitem__(key, value)


class Evolution(Data):
    pass


class Evolutions(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, Evolution):
            value = Evolution(value)
        super().__setitem__(key, value)


class RangedContext(WeaponContext):
    pass


class PrimaryContext(RangedContext):
    pass


class SecondaryContext(RangedContext):
    pass


class MeleeContext(WeaponContext):
    pass

# ------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------

class WeaponEntryData(Data):
    type: str | None = None
    subtype: str | None = None
    disposition: Number = 0.0
    ammo: Data = {}
    attacks: Attacks = Attacks()
    evolutions: Evolutions = Evolutions()



class WeaponData(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, WeaponEntryData):
            value = WeaponEntryData(value)
        super().__setitem__(key, value)

    @property
    def name(self) -> str:
        return next(iter(self))

    @property
    def entry(self) -> WeaponEntryData:
        return self[self.name]


class RangedData(WeaponData):
    pass


class MeleeData(WeaponData):
    pass


class PrimaryData(RangedData):
    pass


class SecondaryData(RangedData):
    pass

# ------------------------------------------------------------------------
# Output Satats
# ------------------------------------------------------------------------

class CalculatedStats(Data):
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
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
    condition_overload: JsonValue
    corpus_damage: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    damage: JsonValue
    electricity: JsonValue
    elements: JsonValue
    fire_rate: JsonValue
    fire_rate_lock: JsonValue
    flat_crit_chance: JsonValue
    flat_crit_damage: JsonValue
    gas: JsonValue
    grineer_damage: JsonValue
    heat: JsonValue
    hunter_munitions: JsonValue
    impact: JsonValue
    infested_damage: JsonValue
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
    murmur_damage: JsonValue
    orokin_damage: JsonValue
    primed_chamber: JsonValue
    puncture: JsonValue
    radiation: JsonValue
    reload_speed: JsonValue
    secondary_encumber: JsonValue
    secondary_enervate: JsonValue
    sentient_damage: JsonValue
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
    equipped: list[str] = []


class SetupContext(Data):
    weapon: WeaponContext = {}
    build: BuildContext = {}
    upgrade: UpgradeContext = {}

# ------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------

class UpgradeEntryData(Data):
    type: str | None = None
    max_rank: int = 0
    compatibility: Data = {}
    incompatibility: list[str] = []
    stats: UpgradeStats = {}



class UpgradeData(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, UpgradeEntryData):
            value = UpgradeEntryData(value)
        super().__setitem__(key, value)

    @property
    def name(self) -> str:
        return next(iter(self))

    @property
    def entry(self) -> UpgradeEntryData:
        return self[self.name]

    @property
    def runtime(self) -> Data:
        runtime = getattr(self, "_runtime", None)
        if runtime is None:
            runtime = Data()
            object.__setattr__(self, "_runtime", runtime)
        return runtime


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
    condition_overload: Mapping[str, Number | str] = {"value": 0.0, "max_stacks": 0}
    corpus_damage: Number = 0.0
    fire_rate: Number = 0.0
    fire_rate_lock: bool = False
    flat_crit_chance: Number = 0.0
    flat_crit_damage: Number = 0.0
    grineer_damage: Number = 0.0
    hunter_munitions: Number = 0.0
    internal_bleeding: Number = 0.0
    infested_damage: Number = 0.0
    magazine_capacity: Number = 0.0
    melee_doughty: Number = 0.0
    melee_duplicate: Number = 0.0
    multiplicative_base_damage: Number = 0.0
    multiplicative_crit_chance: Number = 0.0
    multiplicative_fire_rate: Number = 0.0
    multiplicative_weakpoint_crit_chance: Number = 0.0
    multishot: Number = 0.0
    multishot_lock: bool = False
    murmur_damage: Number = 0.0
    orokin_damage: Number = 0.0
    primed_chamber: Number = 0.0
    reload_speed: Number = 0.0
    secondary_encumber: Number = 0.0
    secondary_enervate: Number = 0.0
    sentient_damage: Number = 0.0
    status_chance: Number = 0.0
    status_damage: Number = 0.0
    vigilante_bonus: Number = 0.0
    weakpoint_crit_chance: Number = 0.0
    weakpoint_damage: Number = 0.0
