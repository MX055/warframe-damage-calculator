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


def seed_base_stats(*, attack: Attack, ammo: dict | object, stats_type: Callable[..., CalculatedStats], evolutions: ResolvedEvolutionStat, distribute_flat: Callable[[Dist, Number], Dist], ability_strength: Number | None = None) -> tuple[CalculatedStats, Dist]:
    """Build base CalculatedStats and the original damage Dist used by GunCO.

    For exalted / pseudo-exalted weapons, `ability_strength` is a multiplier on
    arsenal base damage (1.0 = 100% Strength) applied before evolution flats.
    """
    stats = dict(attack.stats)
    falloff = stats.pop("falloff", None) or {}
    attack_speed = attack.stats.attack_speed if "attack_speed" in attack.stats else attack.stats.fire_rate
    stats.update({"attack_speed": attack_speed, "magazine_capacity": ammo.get("magazine_size", 1) if hasattr(ammo, "get") else 1, "ammo_maximum": ammo.get("ammo_maximum", 0) if hasattr(ammo, "get") else 0, "reload_speed": ammo.get("reload_time", 0) if hasattr(ammo, "get") else 0, "recharge_rate": ammo.get("recharge_rate", 0) if hasattr(ammo, "get") else 0, "start_range": falloff.get("start_range", 0), "end_range": falloff.get("end_range", 0), "final_multiplier": falloff.get("final_multiplier", 1)})
    base = CalculatedStats(stats_type(stats).with_defaults())
    if ability_strength is not None:
        base.damage = base.damage * max(float(ability_strength), 0.0)
    original_damage = Dist(dict(base.damage))

    evo = evolutions.base
    if evo.damage: base.damage = base.damage + distribute_flat(base.damage, evo.damage)
    base.crit_chance = max(base.crit_chance + evo.crit_chance, 0)
    base.crit_damage = max(base.crit_damage + evo.crit_damage, 1)
    base.status_chance = max(base.status_chance + evo.status_chance, 0)
    base.magazine_capacity = max(base.magazine_capacity + evo.magazine_capacity, 1)
    for key in ("punch_through", "zoom", "accuracy", "recoil", "projectile_speed", "range"):
        base[key] = float(base[key] if key in base else 0) + float(getattr(evo, key) or 0)
    # Incarnon "ammo capacity to N" perks replace reserve ammo rather than stacking.
    if evo.ammo_maximum: base.ammo_maximum = evo.ammo_maximum
    if evo.noise_level is not None: base.noise_level = "silent" if "silent" in (base.noise_level if "noise_level" in base else None, evo.noise_level) else evo.noise_level
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
    crit_from = evolutions.additive.crit_from_status
    if isinstance(crit_from, ConversionBonus) and float(crit_from.value):
        cap = float(crit_from.max) if float(crit_from.max) else float("inf")
        bonus = min(cap, float(crit_from.value) * provisional_status_chance(base=base, build=build, evolutions=evolutions))
        base.crit_chance = max(float(base.crit_chance) + bonus, 0)

    status_from = evolutions.additive.status_from_crit
    if isinstance(status_from, ConversionBonus) and float(status_from.value):
        cap = float(status_from.max) if float(status_from.max) else float("inf")
        bonus = min(cap, float(status_from.value) * provisional_crit_chance(base=base, build=build, evolutions=evolutions, crit_upgrade_multiplier=crit_upgrade_multiplier))
        base.status_chance = max(float(base.status_chance) + bonus, 0)


def compute_shared_modded_scalars(*, base: CalculatedStats, build: ResolvedStat, evolutions: ResolvedEvolutionStat, modded: ModdedStats, attack: Attack, crit_upgrade_multiplier: float) -> None:
    """Fill shared modded scalar fields (no damage Dist, no category-specific stats)."""
    # Tier 1 only here; GunCO may add into this factor. Tiers >= 2 fold in compute_shared_effective.
    modded.multiplicative.damage_bonus = max(1 + build.multiplicative.damage_bonus + float(evolutions.multiplicative.damage_bonus or 0), 1)
    modded.additive.damage_bonus = max(1 + build.additive.damage_bonus + evolutions.additive.damage_bonus + float(attack.stats.damage_bonus or 0), 0)
    modded.additive.corpus_damage = max(1 + build.additive.corpus_damage, 1)
    modded.additive.grineer_damage = max(1 + build.additive.grineer_damage, 1)
    modded.additive.infested_damage = max(1 + build.additive.infested_damage, 1)
    modded.additive.orokin_damage = max(1 + build.additive.orokin_damage, 1)
    modded.additive.murmur_damage = max(1 + build.additive.murmur_damage, 1)
    modded.additive.sentient_damage = max(1 + build.additive.sentient_damage, 1)
    modded.flat.crit_chance = build.flat.crit_chance * crit_upgrade_multiplier + evolutions.flat.crit_chance
    modded.multiplicative.crit_chance = max(1 + build.multiplicative.crit_chance, 1)
    modded.additive.crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance * crit_upgrade_multiplier), 0)
    modded.flat.crit_damage = max(build.flat.crit_damage + evolutions.flat.crit_damage, 0)
    modded.additive.crit_damage = max(base.crit_damage * (1 + build.additive.crit_damage), 1)
    modded.flat.status_chance = build.flat.status_chance + evolutions.flat.status_chance
    modded.additive.status_chance = max(base.status_chance * (1 + build.additive.status_chance + evolutions.additive.status_chance), 0)
    modded.additive.status_damage = max(1 + build.additive.status_damage, 1)
    modded.additive.status_duration = max(base.status_duration * (1 + build.additive.status_duration + evolutions.additive.status_duration), 0)
    modded.additive.non_crit_bonus_damage = max(build.additive.non_crit_bonus_damage + evolutions.additive.non_crit_bonus_damage, 0)
    modded.additive.non_crit_bonus_chance = max(build.additive.non_crit_bonus_chance, evolutions.additive.non_crit_bonus_chance, 0)
    modded.additive.range = max(float(base.range if "range" in base else 0) + build.additive.range + build.flat.range + evolutions.additive.range + evolutions.flat.range, 0)
    modded.additive.punch_through = max(float(base.punch_through if "punch_through" in base else 0) + build.additive.punch_through + build.flat.punch_through + evolutions.additive.punch_through + evolutions.flat.punch_through, 0)
    modded.additive.multishot = max(float(base.multishot if "multishot" in base else 1), 1)
    modded.base.noise_level = "silent" if "silent" in (base.noise_level if "noise_level" in base else None, build.base.noise_level, evolutions.base.noise_level) else next((n for n in (base.noise_level if "noise_level" in base else None, build.base.noise_level, evolutions.base.noise_level) if n is not None), "alarming")


def compute_shared_effective(*, base: CalculatedStats, modded: ModdedStats, effective: CalculatedStats, build: ResolvedStat | None = None, evolutions: ResolvedEvolutionStat | None = None) -> None:
    """Fold shared modded scalars into effective stats."""
    higher = formulas.fold_multiplicative_tiers(build, evolutions, stat="damage_bonus", min_tier=2) if build is not None else 1.0
    damage_factor = modded.multiplicative.damage_bonus * higher
    effective.forced_procs = base.forced_procs
    effective.damage_bonus = modded.additive.damage_bonus * damage_factor
    effective.damage = damage_factor * modded.additive.damage
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
    effective.punch_through = modded.additive.punch_through
    effective.multishot = modded.additive.multishot
    effective.noise_level = modded.base.noise_level or (base.noise_level if "noise_level" in base else None) or "alarming"
