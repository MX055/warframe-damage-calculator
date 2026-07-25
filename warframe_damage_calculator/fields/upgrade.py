from collections.abc import Mapping

from ..core.data import Data
from ..core.dist import Dist
from ..utils.types import JsonValue, Number


class UpgradeStats(Data):
    accuracy: JsonValue
    ammo_efficiency: JsonValue
    ammo_maximum: JsonValue
    attack_speed: JsonValue
    cold: JsonValue
    corrosive: JsonValue
    corpus_damage: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    crit_reset_charges: JsonValue
    damage: JsonValue
    damage_bonus: JsonValue
    duplicated_hit: JsonValue
    electricity: JsonValue
    elements: JsonValue
    fire_rate: JsonValue
    fire_rate_lock: JsonValue
    gas: JsonValue
    grineer_damage: JsonValue
    heat: JsonValue
    heavy_attack_efficiency: JsonValue
    heavy_attack_speed: JsonValue
    impact: JsonValue
    infested_damage: JsonValue
    initial_combo: JsonValue
    magazine_capacity: JsonValue
    magnetic: JsonValue
    multishot: JsonValue
    multishot_lock: JsonValue
    murmur_damage: JsonValue
    noise_level: JsonValue
    non_crit_bonus_chance: JsonValue
    non_crit_bonus_damage: JsonValue
    orokin_damage: JsonValue
    projectile_speed: JsonValue
    punch_through: JsonValue
    puncture: JsonValue
    random_proc: JsonValue
    range: JsonValue
    radiation: JsonValue
    recoil: JsonValue
    reload_speed: JsonValue
    sentient_damage: JsonValue
    slam_damage: JsonValue
    slash: JsonValue
    slash_proc: JsonValue
    slide_crit_chance: JsonValue
    status_chance: JsonValue
    status_damage: JsonValue
    status_duration: JsonValue
    toxin: JsonValue
    viral: JsonValue
    weakpoint_crit_chance: JsonValue
    weakpoint_damage: JsonValue
    zoom: JsonValue


class StanceCombo(Data):
    name: str = ""
    multiplier: Number = 1.0
    hits: Number = 0
    duration: Number = 0.0


class StanceCombos(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, StanceCombo):
            value = StanceCombo(value)
        super().__setitem__(key, value)


class UpgradeData(Data):
    name: str = ""
    type: str | None = None
    max_rank: int = 0
    compatibility: Data = {}
    incompatibility: list[str] = []
    stats: UpgradeStats = {}
    combos: StanceCombos = {}

    @property
    def runtime(self) -> Data:
        runtime = getattr(self, "_runtime", None)
        if runtime is None:
            runtime = Data()
            object.__setattr__(self, "_runtime", runtime)
        return runtime


class ResolvedModeStats(Data):
    damage: Dist = Dist()
    elements: Data = Data()
    accuracy: Number = 0.0
    ammo_efficiency: Number = 0.0
    ammo_maximum: Number = 0.0
    attack_speed: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 0.0
    condition_overload: Mapping[str, Number | str] = {"value": 0.0, "max_stacks": 0}
    status_effect_stacks: list = []
    corpus_damage: Number = 0.0
    damage_bonus: Number = 0.0
    fire_rate: Number = 0.0
    fire_rate_lock: bool = False
    grineer_damage: Number = 0.0
    heavy_attack_speed: Number = 0.0
    heavy_attack_efficiency: Number = 0.0
    initial_combo: Number = 0.0
    infested_damage: Number = 0.0
    magazine_capacity: Number = 0.0
    multishot: Number = 0.0
    multishot_lock: bool = False
    murmur_damage: Number = 0.0
    noise_level: str | None = None
    non_crit_bonus_chance: Number = 0.0
    non_crit_bonus_damage: Number = 0.0
    orokin_damage: Number = 0.0
    projectile_speed: Number = 0.0
    punch_through: Number = 0.0
    range: Number = 0.0
    recoil: Number = 0.0
    reload_speed: Number = 0.0
    sentient_damage: Number = 0.0
    slam_damage: Number = 0.0
    slide_crit_chance: Number = 0.0
    status_chance: Number = 0.0
    status_damage: Number = 0.0
    status_duration: Number = 0.0
    weakpoint_crit_chance: Number = 0.0
    weakpoint_damage: Number = 0.0
    zoom: Number = 0.0


class ResolvedStat(Data):
    proportional: ResolvedModeStats = ResolvedModeStats()
    base: ResolvedModeStats = ResolvedModeStats()
    flat: ResolvedModeStats = ResolvedModeStats()
    # Named product families (bonus, chamber, charge, status, …). Same family adds; different multiply.
    multiplicative_families: Data = Data()
    magazine_position: list = []
    stacking_reset: list = []
    application_chance: list = []
    conversions: list = []
