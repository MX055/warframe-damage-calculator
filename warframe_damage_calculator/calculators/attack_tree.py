"""Attack-tree traversal and aggregation, separate from per-attack stat formulas."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping

from ..fields.attack_result import AttackResult
from ..fields.calculated import AverageStats
from ..fields.weapon_data import Attack


def validate_attack_cycles(attacks: Mapping[str, Attack]) -> None:
    def walk(name: str, ancestors: frozenset[str]) -> None:
        if name in ancestors: raise ValueError(f"cyclic attack relationship detected: {name}")
        if name not in attacks: return
        next_ancestors = ancestors | {name}
        for child in attacks[name].children: walk(child, next_ancestors)

    for name in attacks: walk(name, frozenset())


def needed_attack_names(attacks: Mapping[str, Attack], selected: str) -> set[str]:
    needed = {selected}
    pending = [selected]
    while pending:
        name = pending.pop()
        attack = attacks.get(name)
        if attack is None: continue
        for child in attack.children:
            if child not in needed and child in attacks:
                needed.add(child)
                pending.append(child)
    return needed


def walk_tree(name: str, results: Mapping[str, AttackResult], ancestors: frozenset[str] | None = None) -> Iterator[AttackResult]:
    ancestors = frozenset() if ancestors is None else ancestors
    if name in ancestors: raise ValueError(f"cyclic attack relationship detected: {name}")
    result = results[name]
    yield result
    next_ancestors = ancestors | {name}
    for child in result.children:
        if child in results: yield from walk_tree(child, results, next_ancestors)


def fold_attack_tree(root: AttackResult, tree: list[AttackResult], *, attack_rate: float) -> AverageStats:
    """Sum per-attack average damage; scale DPS by the root attack's sustained rate."""
    final = root.average.copy()
    final.flat_dph = sum(item.average.get("flat_dph", 0) for item in tree)
    final.flat_dotph = sum(item.average.get("flat_dotph", 0) for item in tree)
    final.total_dph = final.flat_dph + final.flat_dotph

    final.flat_dps = final.flat_dph * attack_rate
    final.flat_dotps = final.flat_dotph * attack_rate
    final.total_dps = final.total_dph * attack_rate

    if any("flat_weakpoint_dph" in item.average for item in tree):
        final.flat_weakpoint_dph = sum(item.average.get("flat_weakpoint_dph", 0) for item in tree)
        final.flat_weakpoint_dotph = sum(item.average.get("flat_weakpoint_dotph", 0) for item in tree)
        final.total_weakpoint_dph = final.flat_weakpoint_dph + final.flat_weakpoint_dotph
        final.flat_weakpoint_dps = final.flat_weakpoint_dph * attack_rate
        final.flat_weakpoint_dotps = final.flat_weakpoint_dotph * attack_rate
        final.total_weakpoint_dps = final.total_weakpoint_dph * attack_rate
    return final


def compute_attack_results(*, attacks: Mapping[str, Attack], selected: str, compute_attack: Callable[[str, Attack], AttackResult], attack_rate_for: Callable[[AttackResult], float]) -> dict[str, AttackResult]:
    needed = needed_attack_names(attacks, selected)
    results = {name: compute_attack(name, attacks[name]) for name in needed}
    for name, result in results.items():
        result.final = fold_attack_tree(result, list(walk_tree(name, results)), attack_rate=attack_rate_for(result))
    return results
