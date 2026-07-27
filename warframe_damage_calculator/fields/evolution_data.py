from ..core.data import Data
from ..core.dist import Dist
from ..utils.types import JsonValue, Number
from .typed_mapping import TypedMapping
from .effect_stats import DeferredEffectLists, RawEffectStats, ResolvedScalarStats


class EvolutionStats(RawEffectStats):
    crit_from_status: JsonValue
    damage_types: JsonValue
    forced_procs: JsonValue
    impact_to_puncture_conversion: JsonValue
    status_from_crit: JsonValue


class EvolutionPerk(Data):
    description: str = ""
    stats: EvolutionStats = EvolutionStats()


class EvolutionTier(TypedMapping):
    _item_type = EvolutionPerk


class Evolutions(TypedMapping):
    _item_type = EvolutionTier


class ConversionBonus(Data):
    value: Number = 0.0
    max: Number = 0.0


class ResolvedEvolutionModeStats(ResolvedScalarStats):
    crit_from_status: ConversionBonus = ConversionBonus()
    damage: Number = 0.0
    damage_types: Dist = Dist()
    forced_procs: Dist = Dist()
    impact_to_puncture_conversion: Number = 0.0
    status_from_crit: ConversionBonus = ConversionBonus()


class ResolvedEvolutionMultiplicativeFamilies(Data):
    pass


class ResolvedEvolutionStat(DeferredEffectLists):
    proportional: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    base: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    flat: ResolvedEvolutionModeStats = ResolvedEvolutionModeStats()
    multiplicative_families: ResolvedEvolutionMultiplicativeFamilies = ResolvedEvolutionMultiplicativeFamilies()
