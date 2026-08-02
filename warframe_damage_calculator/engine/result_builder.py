from __future__ import annotations

from collections.abc import Mapping

from ..domain.results import AggregateResult, AverageResult, CalculatedAttack, DamageMetrics, DamageResult, SpatialResult, StatusResult
from ..domain.status import StatusModel
from .models.attack import AttackResult, AverageAttackStats, SpatialMetrics


def _damage_metrics(source: AverageAttackStats | SpatialMetrics) -> DamageMetrics | None:
    direct_dph = source.flat_dph
    dot_dph = source.flat_dotph
    total_dph = source.total_dph
    direct_dps = source.flat_dps
    dot_dps = source.flat_dotps
    total_dps = source.total_dps
    if all(value is None for value in (direct_dph, dot_dph, total_dph, direct_dps, dot_dps, total_dps)): return None
    return DamageMetrics(float(direct_dph or 0), float(dot_dph or 0), float(total_dph or 0), float(direct_dps or 0), float(dot_dps or 0), float(total_dps or 0))


def _status_from_model(model: StatusModel, effects: Mapping[str, float]) -> StatusResult:
    kinds = set(model.damage) | set(model.forced_procs) | set(model.extra_proc_counts) | set(effects)
    sustained = {}
    for kind in kinds:
        value = float(model.expected_active_stacks(kind))
        if value: sustained[kind] = value
    return StatusResult(float(model.expected_procs_per_attack), sustained, dict(effects))


def _status(result: AttackResult) -> StatusResult:
    return _status_from_model(result.effective.status_model, result.status_effects)


def _spatial(result: AttackResult) -> SpatialResult | None:
    spatial = result.spatial
    if spatial.dimension is None or spatial.damage_mass is None: return None
    metrics = _damage_metrics(spatial) or DamageMetrics(0, 0, 0, 0, 0, 0)
    return SpatialResult(int(spatial.dimension), float(spatial.falloff_multiplier or 1), float(spatial.damage_mass), metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps)


def _damage_result(source: AverageAttackStats) -> DamageResult:
    metrics = _damage_metrics(source) or DamageMetrics(0, 0, 0, 0, 0, 0)
    return DamageResult(metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps)


def _average_result(source: AverageAttackStats) -> AverageResult:
    damage = _damage_result(source)
    return AverageResult(damage=source.damage, crit_chance=float(source.crit_chance), crit_damage=float(source.crit_damage), status_chance=float(source.status_chance), status_duration=float(source.status_duration), multishot=float(source.multishot), fire_rate=float(source.fire_rate), magazine_capacity=float(source.magazine_capacity), reload_time=float(source.reload_time), ammo_cost=float(source.ammo_cost), ammo_efficiency=float(source.ammo_efficiency), punch_through=float(source.punch_through), burst_count=float(source.burst_count), burst_delay=float(source.burst_delay), charge_time=float(source.charge_time), attack_speed=float(source.attack_speed), heavy_attack_speed=float(source.heavy_attack_speed), heavy_attack_efficiency=float(source.heavy_attack_efficiency), initial_combo=float(source.initial_combo), direct_dph=damage.direct_dph, dot_dph=damage.dot_dph, total_dph=damage.total_dph, direct_dps=damage.direct_dps, dot_dps=damage.dot_dps, total_dps=damage.total_dps, crit_multiplier=float(source.crit_multiplier), weakpoint_crit_chance=float(source.weakpoint_crit_chance), weakpoint_crit_multiplier=float(source.weakpoint_crit_multiplier), attack_rate=float(source.attack_rate), first_shot_damage_multiplier=float(source.first_shot_damage_multiplier), combo_multiplier=float(source.combo_multiplier), melee_duplicate_multiplier=float(source.melee_duplicate_multiplier), melee_doughty_bonus=float(source.melee_doughty_bonus), crit_tier_bonus=float(source.crit_tier_bonus), weakpoint_crit_tier_bonus=float(source.weakpoint_crit_tier_bonus), secondary_enervate_bonus=float(source.secondary_enervate_bonus), weakpoint_secondary_enervate_bonus=float(source.weakpoint_secondary_enervate_bonus), falloff_multiplier=float(source.falloff_multiplier))


def build_calculated_attack(result: AttackResult) -> CalculatedAttack:
    return CalculatedAttack(result.base, result.modded, result.effective, result.upgrades, result.evolutions, _average_result(result.average), _status(result), _spatial(result))


def build_aggregate(average: AverageAttackStats, status_model: StatusModel, status_effects: Mapping[str, float]) -> AggregateResult:
    return AggregateResult(_damage_result(average), _status_from_model(status_model, status_effects))
