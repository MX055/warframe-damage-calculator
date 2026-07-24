from collections.abc import Mapping

from ..core.data import Data
from ..core.dist import Dist
from ..utils.types import JsonValue, Number


class UpgradeStats(Data):
    ammo_efficiency: JsonValue
    attack_speed: JsonValue
    cold: JsonValue
    corrosive: JsonValue
    condition_overload: JsonValue
    status_effect_stacks: JsonValue
    corpus_damage: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    damage: JsonValue
    damage_bonus: JsonValue
    electricity: JsonValue
    elements: JsonValue
    fire_rate: JsonValue
    fire_rate_lock: JsonValue
    gas: JsonValue
    grineer_damage: JsonValue
    heat: JsonValue
    heavy_attack_speed: JsonValue
    hunter_munitions: JsonValue
    impact: JsonValue
    infested_damage: JsonValue
    initial_combo: JsonValue
    internal_bleeding: JsonValue
    magazine_capacity: JsonValue
    magnetic: JsonValue
    melee_doughty: JsonValue
    melee_duplicate: JsonValue
    multishot: JsonValue
    multishot_lock: JsonValue
    murmur_damage: JsonValue
    non_crit_bonus_chance: JsonValue
    non_crit_bonus_damage: JsonValue
    orokin_damage: JsonValue
    primed_chamber: JsonValue
    projectile_speed: JsonValue
    puncture: JsonValue
    range: JsonValue
    radiation: JsonValue
    reload_speed: JsonValue
    secondary_encumber: JsonValue
    secondary_enervate: JsonValue
    sentient_damage: JsonValue
    slam_damage: JsonValue
    slash: JsonValue
    slide_crit_chance: JsonValue
    status_chance: JsonValue
    status_damage: JsonValue
    status_duration: JsonValue
    toxin: JsonValue
    vigilante_bonus: JsonValue
    viral: JsonValue
    weakpoint_crit_chance: JsonValue
    weakpoint_damage: JsonValue


class UpgradeData(Data):
    name: str = ""
    type: str | None = None
    max_rank: int = 0
    compatibility: Data = {}
    incompatibility: list[str] = []
    stats: UpgradeStats = {}

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
    ammo_efficiency: Number = 0.0
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
    hunter_munitions: Number = 0.0
    internal_bleeding: Number = 0.0
    initial_combo: Number = 0.0
    infested_damage: Number = 0.0
    magazine_capacity: Number = 0.0
    melee_doughty: Number = 0.0
    melee_duplicate: Number = 0.0
    multishot: Number = 0.0
    multishot_lock: bool = False
    murmur_damage: Number = 0.0
    non_crit_bonus_chance: Number = 0.0
    non_crit_bonus_damage: Number = 0.0
    orokin_damage: Number = 0.0
    primed_chamber: Number = 0.0
    projectile_speed: Number = 0.0
    range: Number = 0.0
    reload_speed: Number = 0.0
    secondary_encumber: Number = 0.0
    secondary_enervate: Number = 0.0
    sentient_damage: Number = 0.0
    slam_damage: Number = 0.0
    slide_crit_chance: Number = 0.0
    status_chance: Number = 0.0
    status_damage: Number = 0.0
    status_duration: Number = 0.0
    vigilante_bonus: Number = 0.0
    weakpoint_crit_chance: Number = 0.0
    weakpoint_damage: Number = 0.0


class ResolvedStat(Data):
    additive: ResolvedModeStats = ResolvedModeStats()
    multiplicative: ResolvedModeStats = ResolvedModeStats()
    base: ResolvedModeStats = ResolvedModeStats()
    flat: ResolvedModeStats = ResolvedModeStats()
