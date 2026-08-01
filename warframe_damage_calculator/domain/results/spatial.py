from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpatialDamageMetrics:
    direct_dph_mass: float
    dot_dph_mass: float
    total_dph_mass: float
    direct_dps_mass: float
    dot_dps_mass: float
    total_dps_mass: float


@dataclass(frozen=True, slots=True)
class SpatialResult:
    dimension: int
    falloff_multiplier: float
    damage_mass: float
    direct_dph_mass: float
    dot_dph_mass: float
    total_dph_mass: float
    direct_dps_mass: float
    dot_dps_mass: float
    total_dps_mass: float
