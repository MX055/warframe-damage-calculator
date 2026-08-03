from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttackSpatialMetrics:
    punch_through: float
    falloff_multiplier: float
    dimension: int | None = None
    damage_mass: float | None = None
    direct_dph_mass: float | None = None
    dot_dph_mass: float | None = None
    total_dph_mass: float | None = None
    direct_dps_mass: float | None = None
    dot_dps_mass: float | None = None
    total_dps_mass: float | None = None
