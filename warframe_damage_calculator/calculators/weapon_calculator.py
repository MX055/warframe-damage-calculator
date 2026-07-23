from typing import Any, Iterator

from ..models.build import Build
from ..fields.attack_result import AttackResult, AttackResults
from ..fields.calculated import AverageStats
from ..models.upgrade import Upgrade
from .attack_calculator import AttackCalculator


class WeaponCalculator:
    attack_calculator_type = AttackCalculator

    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon
        self.attack_calculator = self.attack_calculator_type(weapon)
        self.attacks = AttackResults()
        self.combined = AverageStats()
        self.recompute()

    def _resolved_build(self) -> Any:
        data = self.weapon.data
        evolutions = (
            Upgrade({
                "name": f"evolution {tier} perk {perk}",
                "type": "evolution",
                "max_rank": 0,
                "compatibility": {"types": []},
                "stats": data.evolutions[str(tier)][str(perk)].get("stats", {}),
            })
            for tier, perk in self.weapon._evolutions.items()
        )
        build = Build(*self.weapon.build, *evolutions)
        build.stats.resolve(data)
        return build.stats.total.copy()

    def _validate_attack_cycles(self) -> None:
        attacks = self.weapon.data.attacks

        def walk(name: str, ancestors: frozenset[str]) -> None:
            if name in ancestors:
                raise ValueError(f"cyclic attack relationship detected: {name}")
            if name not in attacks:
                return
            next_ancestors = ancestors | {name}
            for child in attacks[name].children:
                walk(child, next_ancestors)

        for name in attacks:
            walk(name, frozenset())

    def _walk_selected(self, name: str, ancestors: frozenset[str] | None = None) -> Iterator[AttackResult]:
        ancestors = frozenset() if ancestors is None else ancestors
        if name in ancestors:
            raise ValueError(f"cyclic attack relationship detected: {name}")
        result = self.attacks[name]
        yield result
        next_ancestors = ancestors | {name}
        for child in result.children:
            if child in self.attacks:
                yield from self._walk_selected(child, next_ancestors)

    def _attack_name(self) -> str:
        return next(name for name, attack in self.weapon.data.attacks.items() if attack is self.weapon._attack)

    def _compute_combined(self, selected: AttackResult, results: list[AttackResult]) -> AverageStats:
        combined = selected.average.copy()
        combined.flat_dph = sum(item.average.get("flat_dph", 0) for item in results)
        combined.flat_dotph = sum(item.average.get("flat_dotph", 0) for item in results)
        combined.total_dph = combined.flat_dph + combined.flat_dotph

        attack_rate = self.attack_calculator._effective_attacks_per_second(selected)
        combined.flat_dps = combined.flat_dph * attack_rate
        combined.flat_dotps = combined.flat_dotph * attack_rate
        combined.total_dps = combined.total_dph * attack_rate

        if any("flat_weakpoint_dph" in item.average for item in results):
            combined.flat_weakpoint_dph = sum(item.average.get("flat_weakpoint_dph", 0) for item in results)
            combined.flat_weakpoint_dotph = sum(item.average.get("flat_weakpoint_dotph", 0) for item in results)
            combined.total_weakpoint_dph = combined.flat_weakpoint_dph + combined.flat_weakpoint_dotph
            combined.flat_weakpoint_dps = combined.flat_weakpoint_dph * attack_rate
            combined.flat_weakpoint_dotps = combined.flat_weakpoint_dotph * attack_rate
            combined.total_weakpoint_dps = combined.total_weakpoint_dph * attack_rate
        return combined

    def recompute(self) -> None:
        self._validate_attack_cycles()
        resolved = self._resolved_build()
        self.attack_calculator = self.attack_calculator_type(self.weapon)
        self.attacks = AttackResults({
            name: self.attack_calculator.compute(name, attack, resolved)
            for name, attack in self.weapon.data.attacks.items()
        })

        attack_name = self._attack_name()
        selected = self.attacks[attack_name]
        self.combined = self._compute_combined(selected, list(self._walk_selected(attack_name)))

    def _average_condition_overload_bonus(self, result: AttackResult, time: float = 5) -> float:
        return self.attack_calculator._average_condition_overload_bonus(result, time)

    def _effective_attacks_per_second(self, result: AttackResult) -> float:
        return self.attack_calculator._effective_attacks_per_second(result)

    def contribution(self, upgrade: Upgrade) -> float:
        full = self.weapon.build
        if all(equipped.data != upgrade.data for equipped in full):
            return 0.0
        reduced = full - upgrade
        full_dps = self.combined.total_dps
        try:
            self.weapon.configure(reduced)
            return full_dps - self.combined.total_dps
        finally:
            self.weapon.configure(full)

    def contribution_values(self) -> dict[str, float]:
        return {str(upgrade.data.name): self.contribution(upgrade) for upgrade in self.weapon.build}

    def contribution_proportions(self) -> dict[str, float]:
        contributions = self.contribution_values()
        total = sum(contributions.values()) or 1
        return {name: contribution / total for name, contribution in contributions.items()}
