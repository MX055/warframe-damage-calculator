from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatusResult:
    expected_procs_per_attack: float
    sustained_procs: dict[str, float]
    effects: dict[str, float]
