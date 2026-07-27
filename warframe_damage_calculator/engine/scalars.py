"""Shared scalar-stat phases: base, evolution conversions, modded scalars, effective fold."""

from __future__ import annotations

from collections.abc import Callable

from ..fields.calculated import CalculatedStats, ModdedStats
from ..fields.evolution_data import ConversionBonus, ResolvedEvolutionStat
from ..fields.upgrade_data import ResolvedStat
from ..fields.weapon_data import Attack
from ..core.dist import Dist
from ..utils.types import Number
from . import formulas
from .effect_schema import NON_CRIT_FAMILY


def _convert_impact_to_puncture(damage: Dist, fraction: Number) -> Dist:
    amount = float(fraction)
    if amount <= 0: return damage
    impact = float(damage.get("impact"))
    if impact <= 0: return damage
    converted = impact * min(amount, 1.0)
    remaining = impact - converted
    values = {name: float(value) for name, value in damage if name != "impact"}
    if remaining: values["impact"] = remaining
    if converted: values["puncture"] = float(values.get("puncture", 0)) + converted
    return Dist({name: value for name, value in values.items() if value})


def seed_base_stats(*, attack: Attack, ammo: dict | object, stats_type: Callable[..., CalculatedStats], evolutions: ResolvedEvolutionStat, distribute_flat: Callable[[Dist, Number], Dist], ability_strength: Number | None = None) -> tuple[CalculatedStats, Dist]:
    stats = dict(attack.stats)
    falloff = stats.pop("falloff", None) or {}
    attack_speed = attack.stats.attack_speed if "attack_speed" in attack.stats else attack.stats.fire_rate
    ammo_get = ammo.get if hasattr(ammo, "get") else (lambda key, default=None: default)
    form = (attack.form or "normal")
    incarnon_charges = float(ammo_get("incarnon_charges", 0) or 0)
    if form == "incarnon" and incarnon_charges > 0:
        magazine_capacity = incarnon_charges
    else:
        magazine_capacity = ammo_get("magazine_size", 1)
    stats.update({"attack_speed": attack_speed, "magazine_capacity": magazine_capacity, "ammo_maximum": ammo_get("ammo_maximum", 0), "reload_speed": ammo_get("reload_time", 0), "recharge_rate": ammo_get("recharge_rate", 0), "start_range": falloff.get("start_range", 0), "end_range": falloff.get("end_range", 0), "final_multiplier": falloff.get("final_multiplier", 1)})
    base = CalculatedStats(stats_type(stats).with_defaults())
    base.forced_procs = base.forced_procs + evolutions.proportional.forced_procs + evolutions.base.forced_procs + evolutions.flat.forced_procs
    if ability_strength is not None:
        base.damage = base.damage * max(float(ability_strength), 0.0)
    conversion = float(evolutions.proportional.impact_to_puncture_conversion or 0) + float(evolutions.base.impact_to_puncture_conversion or 0) + float(evolutions.flat.impact_to_puncture_conversion or 0)
    if conversion: base.damage = _convert_impact_to_puncture(base.damage, conversion)
    original_damage = Dist(dict(base.damage))

    evo = evolutions.base
    if evo.damage: base.damage = base.damage + distribute_flat(base.damage, evo.damage)
    base.crit_chance = max(base.crit_chance + evo.crit_chance, 0)
    base.crit_damage = max(base.crit_damage + evo.crit_damage, 1)
    base.status_chance = max(base.status_chance + evo.status_chance, 0)
    # Mag-size / Extended Volley base adds never apply to Incarnon charge pools.
    if form != "incarnon":
        base.magazine_capacity = max(base.magazine_capacity + evo.magazine_capacity, 1)
    for key in ("punch_through", "zoom", "accuracy", "recoil", "projectile_speed", "range"):
        base[key] = float(base[key] if key in base else 0) + float(getattr(evo, key) or 0)
    if evo.ammo_maximum: base.ammo_maximum = evo.ammo_maximum
    if evo.noise_level is not None: base.noise_level = "silent" if "silent" in (base.noise_level if "noise_level" in base else None, evo.noise_level) else evo.noise_level
    return base, original_damage


def provisional_status_chance(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat) -> float:
    scaled = max(base.status_chance * (1 + build.proportional.status_chance + evolutions.proportional.status_chance), 0)
    flat = build.flat.status_chance + evolutions.flat.status_chance
    return float(formulas.combine_chance(scaled, flat=flat))


def provisional_crit_chance(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, crit_upgrade_multiplier: float) -> float:
    scaled = max(base.crit_chance * (1 + build.proportional.crit_chance * crit_upgrade_multiplier), 0)
    family_factor = formulas.fold_multiplicative_families(build, evolutions, stat="crit_chance")
    flat = build.flat.crit_chance * crit_upgrade_multiplier + evolutions.flat.crit_chance
    return float(formulas.combine_chance(scaled, family_factor, flat))


def apply_evolution_conversions(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, crit_upgrade_multiplier: float) -> None:
    crit_from = evolutions.proportional.crit_from_status
    if isinstance(crit_from, ConversionBonus) and float(crit_from.value):
        cap = float(crit_from.max) if float(crit_from.max) else float("inf")
        bonus = min(cap, float(crit_from.value) * provisional_status_chance(base=base, build=build, evolutions=evolutions))
        base.crit_chance = max(float(base.crit_chance) + bonus, 0)

    status_from = evolutions.proportional.status_from_crit
    if isinstance(status_from, ConversionBonus) and float(status_from.value):
        cap = float(status_from.max) if float(status_from.max) else float("inf")
        bonus = min(cap, float(status_from.value) * provisional_crit_chance(base=base, build=build, evolutions=evolutions, crit_upgrade_multiplier=crit_upgrade_multiplier))
        base.status_chance = max(float(base.status_chance) + bonus, 0)


def compute_shared_modded_scalars(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, modded: ModdedStats, attack: Attack, crit_upgrade_multiplier: float) -> None:
    modded.proportional.damage_bonus = max(1 + build.proportional.damage_bonus + evolutions.proportional.damage_bonus + float(attack.stats.damage_bonus or 0), 0)
    modded.proportional.corpus_damage = max(1 + build.proportional.corpus_damage, 1)
    modded.proportional.grineer_damage = max(1 + build.proportional.grineer_damage, 1)
    modded.proportional.infested_damage = max(1 + build.proportional.infested_damage, 1)
    modded.proportional.orokin_damage = max(1 + build.proportional.orokin_damage, 1)
    modded.proportional.murmur_damage = max(1 + build.proportional.murmur_damage, 1)
    modded.proportional.sentient_damage = max(1 + build.proportional.sentient_damage, 1)
    modded.flat.crit_chance = build.flat.crit_chance * crit_upgrade_multiplier + evolutions.flat.crit_chance
    modded.proportional.crit_chance = max(base.crit_chance * (1 + build.proportional.crit_chance * crit_upgrade_multiplier), 0)
    modded.flat.crit_damage = max(build.flat.crit_damage + evolutions.flat.crit_damage, 0)
    modded.proportional.crit_damage = max(base.crit_damage * (1 + build.proportional.crit_damage), 1)
    modded.flat.status_chance = build.flat.status_chance + evolutions.flat.status_chance
    modded.proportional.status_chance = max(base.status_chance * (1 + build.proportional.status_chance + evolutions.proportional.status_chance), 0)
    modded.proportional.status_damage = max(1 + build.proportional.status_damage, 1)
    modded.proportional.status_duration = max(base.status_duration * (1 + build.proportional.status_duration + evolutions.proportional.status_duration), 0)
    modded.proportional.non_crit_bonus_damage = max(
        formulas.family_bonus(build, evolutions, family=NON_CRIT_FAMILY, stat="damage_bonus")
        + build.proportional.non_crit_bonus_damage
        + evolutions.proportional.non_crit_bonus_damage,
        0,
    )
    modded.proportional.non_crit_bonus_chance = max(build.proportional.non_crit_bonus_chance, evolutions.proportional.non_crit_bonus_chance, 0)
    modded.proportional.range = max(float(base.range if "range" in base else 0) + build.proportional.range + build.flat.range + evolutions.proportional.range + evolutions.flat.range, 0)
    modded.proportional.punch_through = max(float(base.punch_through if "punch_through" in base else 0) + build.proportional.punch_through + build.flat.punch_through + evolutions.proportional.punch_through + evolutions.flat.punch_through, 0)
    modded.proportional.multishot = max(float(base.multishot if "multishot" in base else 1), 1)
    modded.base.noise_level = "silent" if "silent" in (base.noise_level if "noise_level" in base else None, build.base.noise_level, evolutions.base.noise_level) else next((n for n in (base.noise_level if "noise_level" in base else None, build.base.noise_level, evolutions.base.noise_level) if n is not None), "alarming")


def compute_shared_effective(*, base: CalculatedStats, modded: ModdedStats, effective: CalculatedStats, build: ResolvedStat | None = None, evolutions: ResolvedEvolutionStat | None = None) -> None:
    sources = tuple(source for source in (build, evolutions, modded) if source is not None)
    damage_factor = formulas.fold_multiplicative_families(*sources, stat="damage_bonus") if sources else 1.0
    crit_factor = formulas.fold_multiplicative_families(*sources, stat="crit_chance") if sources else 1.0
    effective.forced_procs = base.forced_procs
    effective.damage_bonus = modded.proportional.damage_bonus * damage_factor
    effective.damage = damage_factor * modded.proportional.damage
    effective.corpus_damage = modded.proportional.corpus_damage
    effective.grineer_damage = modded.proportional.grineer_damage
    effective.infested_damage = modded.proportional.infested_damage
    effective.orokin_damage = modded.proportional.orokin_damage
    effective.murmur_damage = modded.proportional.murmur_damage
    effective.sentient_damage = modded.proportional.sentient_damage
    effective.crit_chance = formulas.combine_chance(modded.proportional.crit_chance, crit_factor, modded.flat.crit_chance)
    effective.crit_damage = modded.proportional.crit_damage + modded.flat.crit_damage
    effective.status_chance = formulas.combine_chance(modded.proportional.status_chance, flat=modded.flat.status_chance)
    effective.status_damage = modded.proportional.status_damage
    effective.status_duration = modded.proportional.status_duration
    effective.non_crit_bonus_damage = modded.proportional.non_crit_bonus_damage
    effective.non_crit_bonus_chance = modded.proportional.non_crit_bonus_chance
    effective.range = modded.proportional.range
    effective.punch_through = modded.proportional.punch_through
    effective.multishot = modded.proportional.multishot
    effective.noise_level = modded.base.noise_level or (base.noise_level if "noise_level" in base else None) or "alarming"
