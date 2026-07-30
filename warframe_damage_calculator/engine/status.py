from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import expm1, log1p

from ..domain.damage import Dist


RANDOM_STATUS_TYPES = frozenset({"impact", "puncture", "slash", "heat", "cold", "electricity", "toxin", "blast", "radiation", "gas", "magnetic", "viral", "corrosive"})
EFFECT_STATUS_TYPES = frozenset({"lifted", "knockdown", "ragdoll", "stagger", "big_stagger", "blind", "stun"})
STATUS_TYPES = RANDOM_STATUS_TYPES | EFFECT_STATUS_TYPES | {"void"}
COMBINED_STATUS_COMPONENTS = {
    "blast": ("heat", "cold"),
    "radiation": ("heat", "electricity"),
    "gas": ("heat", "toxin"),
    "magnetic": ("cold", "electricity"),
    "viral": ("cold", "toxin"),
    "corrosive": ("electricity", "toxin"),
}


def sustained_proc_chance(probability: float, attempts: float) -> float:
    if probability <= 0 or attempts <= 0: return 0.0
    if probability >= 1 or attempts == float("inf"): return 1.0
    return float(-expm1(attempts * log1p(-probability)))


def attack_proc_chance(probability: float, attempts: float) -> float:
    if probability <= 0 or attempts <= 0: return 0.0
    if probability >= 1 or attempts == float("inf"): return 1.0
    guaranteed, fractional = divmod(attempts, 1)
    return 1 - (1 - probability) ** guaranteed * (1 - fractional * probability)


@dataclass(frozen=True, slots=True)
class StatusModel:
    damage: Dist
    forced_procs: Dist
    status_chance: float
    attempts_per_attack: float
    attacks_per_second: float
    duration: float
    extra_proc_counts: Dist = field(default_factory=Dist)
    extra_proc_probabilities: Dist = field(default_factory=Dist)
    extra_any_proc_probability: float = 0
    random_proc_probability: float = 0
    random_triggered_procs: Dist = field(default_factory=Dist)
    critical_proc_counts: Dist = field(default_factory=Dist)

    @property
    def attempts_per_second(self) -> float:
        return max(self.attempts_per_attack * self.attacks_per_second, 0)

    def base_proc_count_per_attempt(self, kind: str) -> float:
        return max(self.status_chance, 0) * self.damage.weight(kind) + max(self.forced_procs.get(kind, 0), 0)

    def base_proc_probability_per_attempt(self, kind: str) -> float:
        guaranteed, fractional = divmod(max(self.status_chance, 0), 1)
        weight = self.damage.weight(kind)
        random = 1 - (1 - weight) ** guaranteed * (1 - fractional * weight)
        forced = min(max(self.forced_procs.get(kind, 0), 0), 1)
        return 1 - (1 - random) * (1 - forced)

    def base_any_proc_probability_per_attempt(self) -> float:
        status_weight = sum(self.damage.weight(kind) for kind in STATUS_TYPES)
        guaranteed, fractional = divmod(max(self.status_chance, 0), 1)
        random = 1 - (1 - status_weight) ** guaranteed * (1 - fractional * status_weight)
        forced = min(sum(max(self.forced_procs.get(kind, 0), 0) for kind in STATUS_TYPES), 1)
        return 1 - (1 - random) * (1 - forced)

    def proc_count_per_attack(self, kind: str) -> float:
        random = self.random_proc_probability / len(RANDOM_STATUS_TYPES) if kind in RANDOM_STATUS_TYPES else 0
        return max(self.attempts_per_attack, 0) * self.base_proc_count_per_attempt(kind) + max(self.extra_proc_counts.get(kind, 0), 0) + random

    @property
    def expected_procs_per_attack(self) -> float:
        return sum(self.proc_count_per_attack(kind) for kind in STATUS_TYPES)

    def per_attack_probability(self, kind: str) -> float:
        base = attack_proc_chance(self.base_proc_probability_per_attempt(kind), max(self.attempts_per_attack, 0))
        extra = min(max(self.extra_proc_probabilities.get(kind, 0), 0), 1)
        random = self.random_proc_probability / len(RANDOM_STATUS_TYPES) if kind in RANDOM_STATUS_TYPES else 0
        return 1 - (1 - base) * (1 - extra) * (1 - random)

    def any_proc_probability_per_attack(self) -> float:
        base = attack_proc_chance(self.base_any_proc_probability_per_attempt(), max(self.attempts_per_attack, 0))
        return 1 - (1 - base) * (1 - min(max(self.extra_any_proc_probability, 0), 1))

    def proc_rate(self, kind: str) -> float:
        return self.proc_count_per_attack(kind) * max(self.attacks_per_second, 0)

    def expected_active(self, kind: str, *, duration: float | None = None) -> float:
        lifetime = self.duration if duration is None else duration
        return self.proc_rate(kind) * max(lifetime, 0)

    def probability_active(self, kind: str, *, duration: float | None = None) -> float:
        probability = self.per_attack_probability(kind)
        window = self.duration if duration is None else duration
        return sustained_proc_chance(probability, self.attacks_per_second * max(window, 0))

    def expected_unique(self, maximum: int | None = None) -> float:
        kinds = (set(self.damage) | set(self.forced_procs) | set(self.extra_proc_counts)) & STATUS_TYPES
        if self.random_proc_probability > 0: kinds = kinds | RANDOM_STATUS_TYPES
        expected = sum(min(self.expected_active(kind), 1) for kind in kinds)
        return min(expected, maximum) if maximum is not None else expected

    def expected_stacks(self, kind: str, maximum: int | None, duration: float | None = None) -> float:
        window = self.duration if duration is None else max(duration, 0)
        expected = self.proc_rate(kind) * window
        return min(expected, maximum) if maximum is not None else expected

    def non_damage_effects(self) -> dict[str, float]:
        return {
            "viral": self.expected_stacks("viral", 10),
            "magnetic": self.expected_stacks("magnetic", 10),
            "corrosive": self.expected_stacks("corrosive", 10, self.duration * 4 / 3),
            "heat": self.expected_stacks("heat", 1),
            "cold": self.expected_stacks("cold", 10),
            "puncture": self.expected_stacks("puncture", 5),
            "blast": self.expected_stacks("blast", 10),
            "void": self.expected_stacks("void", 1),
        }

    @classmethod
    def combine(cls, models: list[StatusModel], attacks_per_second: float, duration: float, random_proc_probability: float = 0, random_triggered_procs: Dist | None = None) -> StatusModel:
        triggered = random_triggered_procs or Dist()
        counts = Dist({kind: sum(model.proc_count_per_attack(kind) for model in models) + triggered.get(kind, 0) for kind in STATUS_TYPES})
        probabilities = Dist({
            kind: 1 - _product(1 - model.per_attack_probability(kind) for model in models)
            for kind in STATUS_TYPES
        })
        any_probability = 1 - _product(1 - model.any_proc_probability_per_attack() for model in models)
        critical_counts = Dist({kind: sum(model.critical_proc_counts.get(kind, 0) for model in models) for kind in STATUS_TYPES})
        return cls(Dist(), Dist(), 0, 0, attacks_per_second, duration, counts, probabilities + triggered, any_probability, random_proc_probability, triggered, critical_counts)


def _product(values: Iterable[float]) -> float:
    result = 1.0
    for value in values: result *= float(value)
    return result
