from __future__ import annotations

from collections.abc import Mapping

from ..domain.results import AggregateResult, AttackCriticalMetrics, AttackDamageMetrics, AttackResult, AttackSpatialMetrics, AttackStatusMetrics, AttackTimingMetrics, DamageMetrics, DamageResult
from ..domain.status import StatusModel
from .models.attack import ResolvedAttack, ResolvedAttackMetrics, SpatialMetrics


def _damage_metrics(source: ResolvedAttackMetrics | SpatialMetrics) -> DamageMetrics | None:
    direct_dph = source.flat_dph
    dot_dph = source.flat_dotph
    total_dph = source.total_dph
    direct_dps = source.flat_dps
    dot_dps = source.flat_dotps
    total_dps = source.total_dps
    if all(value is None for value in (direct_dph, dot_dph, total_dph, direct_dps, dot_dps, total_dps)): return None
    return DamageMetrics(float(direct_dph or 0), float(dot_dph or 0), float(total_dph or 0), float(direct_dps or 0), float(dot_dps or 0), float(total_dps or 0))


def _status_from_model(model: StatusModel, effects: Mapping[str, float], *, status_chance: float = 0, status_duration: float = 0) -> AttackStatusMetrics:
    kinds = set(model.damage) | set(model.forced_procs) | set(model.extra_proc_counts) | set(effects)
    sustained = {}
    for kind in kinds:
        value = float(model.expected_active_stacks(kind))
        if value: sustained[kind] = value
    return AttackStatusMetrics(float(status_chance), float(status_duration), float(model.expected_procs_per_attack), sustained, dict(effects))


def _status(result: ResolvedAttack) -> AttackStatusMetrics:
    average = result.average
    return _status_from_model(result.effective.status_model, result.status_effects, status_chance=average.status_chance, status_duration=average.status_duration)


def _spatial(result: ResolvedAttack) -> AttackSpatialMetrics:
    average = result.average
    spatial = result.spatial
    if spatial.dimension is None or spatial.damage_mass is None:
        return AttackSpatialMetrics(float(average.punch_through), float(average.falloff_multiplier))
    metrics = _damage_metrics(spatial) or DamageMetrics(0, 0, 0, 0, 0, 0)
    return AttackSpatialMetrics(float(average.punch_through), float(spatial.falloff_multiplier or average.falloff_multiplier), int(spatial.dimension), float(spatial.damage_mass), metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps)


def _damage_result(source: ResolvedAttackMetrics) -> DamageResult:
    metrics = _damage_metrics(source) or DamageMetrics(0, 0, 0, 0, 0, 0)
    return DamageResult(metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps)


def _attack_damage(source: ResolvedAttackMetrics) -> AttackDamageMetrics:
    metrics = _damage_result(source)
    return AttackDamageMetrics(metrics.direct_dph, metrics.dot_dph, metrics.total_dph, metrics.direct_dps, metrics.dot_dps, metrics.total_dps, source.damage, float(source.first_shot_damage_multiplier), float(source.combo_multiplier))


def _attack_critical(source: ResolvedAttackMetrics) -> AttackCriticalMetrics:
    return AttackCriticalMetrics(float(source.crit_chance), float(source.crit_damage), float(source.crit_multiplier), float(source.crit_tier_bonus), float(source.puncture_status_crit_damage_bonus), float(source.secondary_enervate_bonus), float(source.weak_point_crit_chance), float(source.weak_point_crit_multiplier), float(source.weak_point_crit_tier_bonus), float(source.weak_point_secondary_enervate_bonus))


def _attack_timing(source: ResolvedAttackMetrics) -> AttackTimingMetrics:
    return AttackTimingMetrics(float(source.fire_rate), float(source.attack_speed), float(source.attack_rate), float(source.multishot), float(source.magazine_capacity), float(source.reload_time), float(source.ammo_cost), float(source.ammo_efficiency), float(source.accuracy), float(source.recoil), float(source.burst_count), float(source.burst_delay), float(source.charge_time), float(source.heavy_attack_speed), float(source.heavy_attack_efficiency), float(source.initial_combo))


def build_calculated_attack(result: ResolvedAttack) -> AttackResult:
    average = result.average
    return AttackResult(result.base, result.modded, result.effective, result.upgrades, result.evolutions, _attack_damage(average), _attack_critical(average), _attack_timing(average), _status(result), _spatial(result), result.generated_by, result.generated_from)


def build_aggregate(average: ResolvedAttackMetrics, status_model: StatusModel, status_effects: Mapping[str, float]) -> AggregateResult:
    return AggregateResult(_damage_result(average), _status_from_model(status_model, status_effects, status_chance=average.status_chance, status_duration=average.status_duration))
