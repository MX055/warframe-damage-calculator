"""Sustained status production model, Condition Overload, and status-effect stacks.

Status production is computed from pre-damage scalars only. Condition Overload and
status_effect_stacks consume SustainedStatusModel and do not feed back into status
production within the same pass.

Quantities:
- status_attempts_per_attack: expected multishot (or melee duplicate) hits that can roll status
- per_attack_probability: P(a given status type procs on one attack/shot)
- sustained_attack_rate: sustained attacks/sec used to re-apply statuses over duration
- expected_unique_active_statuses: E[number of distinct status types currently
  active] over one status-duration window (Condition Overload)
- expected_status_stacks: E[proc count of one status type] in that window, capped
  (Cascadia / Frostbite-style status_effect_stacks)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import expm1, log1p
from typing import Literal

from ..fields.calculated import CalculatedStats, ModdedStats
from ..fields.upgrade import ResolvedStat
from ..fields.weapon_data import Attack
from ..utils.types import Number


@dataclass(frozen=True, slots=True)
class SustainedStatusModel:
    """Inputs for sustained status modelling (no damage Dist)."""

    per_attack_probabilities: Mapping[str, float]
    attacks_per_second: float
    status_duration: float
    max_unique_statuses: int
    status_attempts_per_attack: float = 1.0

    @property
    def attempts_during_duration(self) -> float:
        """Sustained attack attempts that can re-apply statuses within one duration window."""
        return self.attacks_per_second * self.status_duration

    def expected_unique_active_statuses(self) -> float:
        """Expected count of distinct status types active during one duration window."""
        maximum = self.max_unique_statuses
        attempts = self.attempts_during_duration
        if maximum <= 0 or attempts <= 0: return 0.0

        distribution = [1.0] + [0.0] * maximum
        for probability in self.per_attack_probabilities.values():
            active = sustained_proc_chance(probability, attempts)
            updated = [0.0] * (maximum + 1)
            for count, chance in enumerate(distribution):
                updated[count] += chance * (1 - active)
                updated[min(count + 1, maximum)] += chance * active
            distribution = updated
        return sum(count * chance for count, chance in enumerate(distribution))

    def expected_status_stacks(self, status: str, max_stacks: int) -> float:
        """Expected stacks from sustained procs of one status type, capped at max_stacks."""
        if max_stacks <= 0: return 0.0
        probability = float(self.per_attack_probabilities.get(status, 0.0))
        attempts = self.attempts_during_duration
        if probability <= 0 or attempts <= 0: return 0.0
        return min(float(max_stacks), attempts * probability)


@dataclass(frozen=True, slots=True)
class ConditionOverloadBonus:
    """Resolved Condition Overload contribution to damage_bonus."""

    bonus: float
    effect: Literal["adds", "multiplies"]
    expected_unique_active: float


def sustained_proc_chance(per_attack_probability: float, attacks_during_duration: float) -> float:
    """P(at least one proc of a type during the duration window)."""
    if per_attack_probability <= 0 or attacks_during_duration <= 0: return 0.0
    if per_attack_probability >= 1 or attacks_during_duration == float("inf"): return 1.0
    return float(-expm1(attacks_during_duration * log1p(-per_attack_probability)))


def condition_overload_bonus(model: SustainedStatusModel, *, value_per_status: Number, co_factor: Number, co_effect: str) -> ConditionOverloadBonus:
    expected = model.expected_unique_active_statuses()
    effect: Literal["adds", "multiplies"] = "multiplies" if co_effect == "multiplies" else "adds"
    return ConditionOverloadBonus(bonus=float(value_per_status) * float(co_factor) * expected, effect=effect, expected_unique_active=expected)


def per_attack_status_probabilities(*, attack: Attack, base: CalculatedStats, build: ResolvedStat, evolution_status_chance: Number, flat_status_chance: Number, status_attempts_per_attack: float) -> dict[str, float]:
    """P(each damage type procs on one attack), including forced procs as certainty."""
    damage = base.damage.apply(build.additive.damage).combine().sorted()
    guaranteed, fractional = divmod(max(attack.stats.status_chance * (1 + build.additive.status_chance + evolution_status_chance) + flat_status_chance, 0), 1)
    guaranteed_hits, fractional_hit = divmod(max(status_attempts_per_attack, 0), 1)
    probabilities: dict[str, float] = {}
    for damage_type in damage.data:
        weight = damage.weight(damage_type)
        miss = (1 - weight) ** guaranteed * (1 - fractional * weight)
        probabilities[damage_type] = 1 - miss ** guaranteed_hits * (1 - fractional_hit + fractional_hit * miss)
    probabilities.update({damage_type: 1.0 for damage_type, count in attack.stats.forced_procs if count > 0})
    return probabilities


def build_sustained_status_model(*, attack: Attack, base: CalculatedStats, modded: ModdedStats, build: ResolvedStat, evolution_status_chance: Number, status_attempts_per_attack: float, sustained_attack_rate: float) -> SustainedStatusModel:
    """Build the sustained status model used by Condition Overload and status_effect_stacks."""
    condition_overload = build.additive.condition_overload
    probabilities = per_attack_status_probabilities(attack=attack, base=base, build=build, evolution_status_chance=evolution_status_chance, flat_status_chance=modded.flat.status_chance, status_attempts_per_attack=status_attempts_per_attack)
    maximum = len(probabilities) if condition_overload.max_stacks == "inf" else int(condition_overload.max_stacks)
    return SustainedStatusModel(per_attack_probabilities=probabilities, attacks_per_second=sustained_attack_rate, status_duration=float(modded.additive.status_duration), max_unique_statuses=maximum, status_attempts_per_attack=status_attempts_per_attack)


def apply_condition_overload(*, modded: ModdedStats, model: SustainedStatusModel, value_per_status: Number, co_factor: Number, co_effect: str) -> ConditionOverloadBonus:
    """Apply CO bonus to modded damage_bonus using only the status model + CO parameters."""
    resolved = condition_overload_bonus(model, value_per_status=value_per_status, co_factor=co_factor, co_effect=co_effect)
    if resolved.effect == "multiplies": modded.multiplicative.damage_bonus = max(modded.multiplicative.damage_bonus + resolved.bonus, 1)
    else: modded.additive.damage_bonus = max(modded.additive.damage_bonus + resolved.bonus, 0)
    return resolved


def status_effect_stack_bonuses(*, model: SustainedStatusModel, entries: list, runtime: Mapping[str, object] | None = None) -> list[tuple[str, str, float]]:
    """Resolve (mode, target_stat, bonus) triples from deferred status_effect_stacks entries.

    Runtime keys `on_<status>_status_effect` override the sustained expectation when set.
    """
    runtime = runtime or {}
    bonuses: list[tuple[str, str, float]] = []
    for entry in entries:
        status = str(entry["status"])
        maximum = int(entry["max_stacks"])
        override = runtime.get(f"on_{status}_status_effect")
        if override is None: override = runtime.get(f"{status}_status_effect")
        stacks = min(float(override), float(maximum)) if override is not None else model.expected_status_stacks(status, maximum)
        if not stacks: continue
        bonuses.append((str(entry.get("mode", "additive")), str(entry["stat"]), float(entry["value"]) * stacks))
    return bonuses
