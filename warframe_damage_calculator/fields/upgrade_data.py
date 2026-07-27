from collections.abc import Mapping

from ..core.data import Data
from ..core.dist import Dist
from ..utils.types import JsonValue, Number
from .typed_mapping import TypedMapping
from .effect_stats import DeferredEffectLists, RawEffectStats, ResolvedScalarStats


class UpgradeStats(RawEffectStats):
    cold: JsonValue
    corrosive: JsonValue
    corpus_damage: JsonValue
    crit_reset_charges: JsonValue
    duplicated_hit: JsonValue
    electricity: JsonValue
    elements: JsonValue
    fire_rate_lock: JsonValue
    gas: JsonValue
    grineer_damage: JsonValue
    heat: JsonValue
    impact: JsonValue
    infested_damage: JsonValue
    magnetic: JsonValue
    multishot_lock: JsonValue
    murmur_damage: JsonValue
    orokin_damage: JsonValue
    puncture: JsonValue
    random_proc: JsonValue
    radiation: JsonValue
    sentient_damage: JsonValue
    slash: JsonValue
    slash_proc: JsonValue
    status_damage: JsonValue
    toxin: JsonValue
    viral: JsonValue
    weakpoint_crit_chance: JsonValue


class StanceCombo(Data):
    name: str = ""
    multiplier: Number = 1.0
    hits: Number = 0
    duration: Number = 0.0


class StanceCombos(TypedMapping):
    _item_type = StanceCombo


class UpgradeCompatibility(Data):
    pass


class UpgradeRuntime(Data):
    pass


class UpgradeData(Data):
    name: str = ""
    type: str | None = None
    max_rank: int = 0
    compatibility: UpgradeCompatibility = UpgradeCompatibility()
    incompatibility: list[str] = []
    stats: UpgradeStats = UpgradeStats()
    combos: StanceCombos = StanceCombos()
    runtime: UpgradeRuntime = UpgradeRuntime()


class ResolvedElements(Data):
    pass


class ResolvedModeStats(ResolvedScalarStats):
    damage: Dist = Dist()
    elements: ResolvedElements = ResolvedElements()
    condition_overload: Mapping[str, Number | str] = {"value": 0.0, "max_stacks": 0}
    status_effect_stacks: list = []
    corpus_damage: Number = 0.0
    fire_rate_lock: bool = False
    grineer_damage: Number = 0.0
    infested_damage: Number = 0.0
    multishot_lock: bool = False
    murmur_damage: Number = 0.0
    orokin_damage: Number = 0.0
    sentient_damage: Number = 0.0
    status_damage: Number = 0.0
    weakpoint_crit_chance: Number = 0.0


class ResolvedMultiplicativeFamilies(Data):
    pass


class ResolvedStat(DeferredEffectLists):
    proportional: ResolvedModeStats = ResolvedModeStats()
    base: ResolvedModeStats = ResolvedModeStats()
    flat: ResolvedModeStats = ResolvedModeStats()
    # Named product families (bonus, chamber, charge, status, …). Same family adds; different multiply.
    multiplicative_families: ResolvedMultiplicativeFamilies = ResolvedMultiplicativeFamilies()
