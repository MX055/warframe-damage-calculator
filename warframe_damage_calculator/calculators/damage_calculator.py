"""Damage Dist construction and DOT helpers.

Condition Overload already lives on modded damage_bonus when this runs;
modded damage Dist is built from that scalar plus evolved/original damage.
"""

from __future__ import annotations

from ..fields.attack_result import AttackResult
from ..fields.calculated import AverageStats, CalculatedStats, ModdedStats
from ..fields.evolution import ResolvedEvolutionStat
from ..fields.upgrade import ResolvedStat
from ..fields.weapon_data import Attack
from ..models.dist import Dist
from ..utils.constants import DOT_MULTIPLIERS
from ..utils.types import Number
from . import formulas


def compute_modded_damage(*, attack: Attack, base: CalculatedStats, original_damage: Dist, build: ResolvedStat, evolutions: ResolvedEvolutionStat, modded: ModdedStats) -> None:
    """Write modded.additive.damage from Serration/CO semantics."""
    evolved = base.damage.apply(build.additive.damage).combine().sorted()
    original = original_damage.apply(build.additive.damage).combine().sorted()
    innate_damage_bonus = float(attack.stats.get("damage_bonus", 0) or 0)
    serration = max(1 + build.additive.damage_bonus + evolutions.additive.damage_bonus + innate_damage_bonus, 0)
    if attack.stats.co_effect == "multiplies":
        modded.additive.damage = modded.additive.damage_bonus * evolved
    else:
        # GunCO / additive CO scales original (pre-evolution) damage only; Serration scales evolved.
        co_bonus = max(float(modded.additive.damage_bonus) - serration, 0)
        modded.additive.damage = serration * evolved + co_bonus * original


def apply_shared_average_factions(*, effective: CalculatedStats, average: AverageStats) -> None:
    average.corpus_damage = effective.corpus_damage
    average.grineer_damage = effective.grineer_damage
    average.infested_damage = effective.infested_damage
    average.orokin_damage = effective.orokin_damage
    average.murmur_damage = effective.murmur_damage
    average.sentient_damage = effective.sentient_damage


def apply_shared_average_crit(*, effective: CalculatedStats, average: AverageStats) -> None:
    """Baseline body-hit crit averages; category calculators may replace these."""
    average.crit_chance = effective.crit_chance
    average.crit_multiplier = formulas.crit_multiplier(average.crit_chance, effective.crit_damage)


def max_faction_damage(average: AverageStats) -> float:
    return max(average.corpus_damage, average.grineer_damage, average.infested_damage, average.orokin_damage, average.murmur_damage, average.sentient_damage)


def flat_dotph(*, base: CalculatedStats, effective: CalculatedStats, average: AverageStats, status_attempts_per_attack: float, weakpoint: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number | None = None) -> float:
    if faction_damage is None: faction_damage = max_faction_damage(average)
    if effective.damage.total_damage() <= 0: return 0.0
    multiplier = formulas.hit_multiplier(average.weakpoint_crit_chance if weakpoint else average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
    regular = sum(factor * effective.damage.get(damage_type) * effective.damage.weight(damage_type) for damage_type, factor in DOT_MULTIPLIERS) * effective.status_chance
    forced = sum(factor * base.forced_procs.get(damage_type) * effective.damage.get(damage_type) for damage_type, factor in DOT_MULTIPLIERS)
    shot_hits = effective.get("multishot", status_attempts_per_attack) if hits is None else hits
    return (regular + forced) * effective.status_duration * effective.status_damage * faction_damage ** 2 * multiplier * damage_multiplier * shot_hits + extra_damage


def flat_dotph_from_result(result: AttackResult, *, status_attempts_per_attack: float, weakpoint: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number | None = None) -> float:
    return flat_dotph(base=result.base, effective=result.effective, average=result.average, status_attempts_per_attack=status_attempts_per_attack, weakpoint=weakpoint, hits=hits, damage_multiplier=damage_multiplier, extra_damage=extra_damage, faction_damage=faction_damage)
