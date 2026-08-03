from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttackStatusMetrics:
    status_chance: float
    status_duration: float
    expected_procs_per_attack: float
    sustained_procs: dict[str, float]
    effects: dict[str, float]
