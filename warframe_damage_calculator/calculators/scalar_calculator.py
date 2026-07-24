"""Shared scalar-stat phases: base, evolution conversions, modded scalars, effective fold.

Consumes explicit layer inputs; mutates the target layer for the current phase.
Category calculators add weapon-specific scalars after the shared fold.
"""

from __future__ import annotations

from collections.abc import Callable

from ..fields.calculated import CalculatedStats, ModdedStats
from ..fields.evolution import ConversionBonus, ResolvedEvolutionStat
from ..fields.upgrade import ResolvedStat
from ..fields.weapon_data import Attack
from ..core.dist import Dist
from ..utils.types import Number
from . import formulas


def seed_base_stats(*, attack: Attack, ammo: dict | object, stats_type: Callable[..., CalculatedStats], evolutions: ResolvedEvolutionStat, distribute_flat: Callable[[Dist, Number], Dist]) -> tuple[CalculatedStats, Dist]:
    """Build base CalculatedStats and the original damage Dist used by GunCO."""
    stats = dict(attack.stats)
    falloff = stats.pop("falloff", None) or {}
    magazine = ammo.get("magazine_size", 1) if hasattr(ammo, "get") else 1
    reload = ammo.get("reload_time", 0) if hasattr(ammo, "get") else 0
    recharge = ammo.get("recharge_rate", 0) if hasattr(ammo, "get") else 0
    stats.update({"attack_speed": attack.stats.fire_rate, "magazine_capacity": magazine, "reload_speed": reload, "recharge_rate": recharge})
    if falloff: stats.update({"start_range": falloff.get("start_range", 0), "end_range": falloff.get("end_range", 0), "final_multiplier": falloff.get("final_multiplier", 1)})
    base = CalculatedStats(stats_type(stats).with_defaults())
    original_damage = Dist(dict(base.damage))

    evo = evolutions.base
    added = float(evo.get("damage", 0) or 0)
    if added: base.damage = base.damage + distribute_flat(base.damage, added)
    base.crit_chance = max(float(base.get("crit_chance", 0) or 0) + float(evo.get("crit_chance", 0) or 0), 0)
    base.crit_damage = max(float(base.get("crit_damage", 0) or 0) + float(evo.get("crit_damage", 0) or 0), 1)
    base.status_chance = max(float(base.get("status_chance", 0) or 0) + float(evo.get("status_chance", 0) or 0), 0)
    base.magazine_capacity = max(float(base.get("magazine_capacity", 0) or 0) + float(evo.get("magazine_capacity", 0) or 0), 1)
    return base, original_damage


def provisional_status_chance(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat) -> float:
    additive = max(base.status_chance * (1 + build.additive.status_chance + evolutions.additive.status_chance), 0)
    flat = build.flat.status_chance + evolutions.flat.status_chance
    return float(formulas.combine_chance(additive, flat=flat))


def provisional_crit_chance(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, crit_upgrade_multiplier: float) -> float:
    additive = max(base.crit_chance * (1 + build.additive.crit_chance * crit_upgrade_multiplier), 0)
    multiplicative = max(1 + build.multiplicative.crit_chance, 1)
    flat = build.flat.crit_chance * crit_upgrade_multiplier + evolutions.flat.crit_chance
    return float(formulas.combine_chance(additive, multiplicative, flat))


def apply_evolution_conversions(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, crit_upgrade_multiplier: float) -> None:
    """Apply crit↔status conversions onto base before modded scalars are derived.

    Order: crit_from_status (provisional status) then status_from_crit (provisional crit after step 1).
    """
    crit_from = evolutions.additive.get("crit_from_status")
    if isinstance(crit_from, ConversionBonus) and float(crit_from.value):
        cap = float(crit_from.max) if float(crit_from.max) else float("inf")
        bonus = min(cap, float(crit_from.value) * provisional_status_chance(base=base, build=build, evolutions=evolutions))
        base.crit_chance = max(float(base.crit_chance) + bonus, 0)

    status_from = evolutions.additive.get("status_from_crit")
    if isinstance(status_from, ConversionBonus) and float(status_from.value):
        cap = float(status_from.max) if float(status_from.max) else float("inf")
        bonus = min(cap, float(status_from.value) * provisional_crit_chance(base=base, build=build, evolutions=evolutions, crit_upgrade_multiplier=crit_upgrade_multiplier))
        base.status_chance = max(float(base.status_chance) + bonus, 0)


def compute_shared_modded_scalars(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, modded: ModdedStats, attack: Attack, crit_upgrade_multiplier: float) -> None:
    """Fill shared modded scalar fields (no damage Dist, no category-specific stats)."""
    innate_damage_bonus = float(attack.stats.get("damage_bonus", 0) or 0)
    crit_mods = crit_upgrade_multiplier
    modded.multiplicative.damage_bonus = max(1 + build.multiplicative.damage_bonus, 1)
    modded.additive.damage_bonus = max(1 + build.additive.damage_bonus + evolutions.additive.damage_bonus + innate_damage_bonus, 0)
    modded.additive.corpus_damage = max(1 + build.additive.corpus_damage, 1)
    modded.additive.grineer_damage = max(1 + build.additive.grineer_damage, 1)
    modded.additive.infested_damage = max(1 + build.additive.infested_damage, 1)
    modded.additive.orokin_damage = max(1 + build.additive.orokin_damage, 1)
    modded.additive.murmur_damage = max(1 + build.additive.murmur_damage, 1)
    modded.additive.sentient_damage = max(1 + build.additive.sentient_damage, 1)
    modded.flat.crit_chance = build.flat.crit_chance * crit_mods + evolutions.flat.crit_chance
    modded.multiplicative.crit_chance = max(1 + build.multiplicative.crit_chance, 1)
    modded.additive.crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance * crit_mods), 0)
    modded.flat.crit_damage = max(build.flat.crit_damage + evolutions.flat.crit_damage, 0)
    modded.additive.crit_damage = max(base.crit_damage * (1 + build.additive.crit_damage), 1)
    modded.flat.status_chance = build.flat.status_chance + evolutions.flat.status_chance
    modded.additive.status_chance = max(base.status_chance * (1 + build.additive.status_chance + evolutions.additive.status_chance), 0)
    modded.additive.status_damage = max(1 + build.additive.status_damage, 1)
    modded.additive.status_duration = max(base.status_duration * (1 + build.additive.status_duration + evolutions.additive.status_duration), 0)
    modded.additive.non_crit_bonus_damage = max(build.additive.non_crit_bonus_damage + evolutions.additive.non_crit_bonus_damage, 0)
    modded.additive.non_crit_bonus_chance = max(build.additive.non_crit_bonus_chance, evolutions.additive.non_crit_bonus_chance, 0)
    modded.additive.range = max(float(base.get("range", 0) or 0) + build.additive.range + build.flat.range + evolutions.additive.range + evolutions.flat.range, 0)


def compute_shared_effective(*, base: CalculatedStats, modded: ModdedStats, effective: CalculatedStats) -> None:
    """Fold shared modded scalars into effective stats."""
    effective.forced_procs = base.forced_procs
    effective.damage_bonus = modded.additive.damage_bonus * modded.multiplicative.damage_bonus
    effective.damage = modded.multiplicative.damage_bonus * modded.additive.damage
    effective.corpus_damage = modded.additive.corpus_damage
    effective.grineer_damage = modded.additive.grineer_damage
    effective.infested_damage = modded.additive.infested_damage
    effective.orokin_damage = modded.additive.orokin_damage
    effective.murmur_damage = modded.additive.murmur_damage
    effective.sentient_damage = modded.additive.sentient_damage
    effective.crit_chance = formulas.combine_chance(modded.additive.crit_chance, modded.multiplicative.crit_chance, modded.flat.crit_chance)
    effective.crit_damage = modded.additive.crit_damage + modded.flat.crit_damage
    effective.status_chance = formulas.combine_chance(modded.additive.status_chance, flat=modded.flat.status_chance)
    effective.status_damage = modded.additive.status_damage
    effective.status_duration = modded.additive.status_duration
    effective.non_crit_bonus_damage = modded.additive.non_crit_bonus_damage
    effective.non_crit_bonus_chance = modded.additive.non_crit_bonus_chance
    effective.range = modded.additive.range
