from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContributionResult:
    contribution: dict[str, float]
    removal: dict[str, float]
    evaluations: int
