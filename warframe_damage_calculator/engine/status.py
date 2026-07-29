from __future__ import annotations

from dataclasses import dataclass
from math import expm1, log1p

from ..domain.damage import Dist


def sustained_proc_chance(probability: float, attempts: float) -> float:
    if probability <= 0 or attempts <= 0: return 0.0
    if probability >= 1 or attempts == float("inf"): return 1.0
    return float(-expm1(attempts * log1p(-probability)))


@dataclass(frozen=True, slots=True)
class StatusModel:
    damage: Dist
    forced_procs: Dist
    status_chance: float
    attempts_per_attack: float
    attacks_per_second: float
    duration: float
    extra_random_proc_chance: float = 0

    @property
    def attempts_per_second(self) -> float:
        return max(self.attempts_per_attack * self.attacks_per_second, 0)

    def per_attack_probability(self, kind: str) -> float:
        guaranteed, fractional = divmod(max(self.status_chance, 0), 1)
        guaranteed_hits, fractional_hit = divmod(max(self.attempts_per_attack, 0), 1)
        weight = self.damage.weight(kind)
        miss = (1 - weight) ** guaranteed * (1 - fractional * weight)
        random = 1 - miss ** guaranteed_hits * (1 - fractional_hit + fractional_hit * miss)
        return 1.0 if self.forced_procs.get(kind, 0) > 0 else random

    def proc_rate(self, kind: str) -> float:
        forced = self.forced_procs.get(kind, 0) * self.attempts_per_attack * self.attacks_per_second
        random = self.attempts_per_second * max(self.status_chance, 0) * self.damage.weight(kind)
        return forced + random

    def expected_active(self, kind: str, *, duration: float | None = None) -> float:
        lifetime = self.duration if duration is None else duration
        return self.proc_rate(kind) * max(lifetime, 0)

    def probability_active(self, kind: str, *, duration: float | None = None) -> float:
        probability = self.per_attack_probability(kind)
        window = self.duration if duration is None else duration
        return sustained_proc_chance(probability, self.attacks_per_second * max(window, 0))

    def expected_unique(self, maximum: int | None = None) -> float:
        kinds = set(self.damage) | set(self.forced_procs)
        expected = sum(self.probability_active(kind) for kind in kinds)
        if self.extra_random_proc_chance:
            expected += min(self.extra_random_proc_chance * self.attempts_per_second * self.duration, max(0, 13 - len(kinds)))
        return min(expected, maximum) if maximum is not None else expected

    def expected_stacks(self, kind: str, maximum: int | None, duration: float | None = None) -> float:
        probability = self.per_attack_probability(kind)
        window = self.duration if duration is None else max(duration, 0)
        if probability <= 0 or self.attacks_per_second <= 0 or window <= 0: return 0.0
        expected = self.attacks_per_second * window * probability
        return min(expected, maximum) if maximum is not None else expected

    def non_damage_effects(self) -> dict[str, float]:
        return {
            "viral": self.expected_stacks("viral", 10),
            "magnetic": self.expected_stacks("magnetic", 10),
            "corrosive": self.expected_stacks("corrosive", 10, self.duration * 4 / 3),
            "heat": self.probability_active("heat"),
        }
