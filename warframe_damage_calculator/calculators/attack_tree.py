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

    def fold_zone(flat_dph: str, flat_dotph: str, total_dph: str, flat_dps: str, flat_dotps: str, total_dps: str) -> None:
        direct = [item.average.get(flat_dph) for item in tree]
        dots = [item.average.get(flat_dotph) for item in tree]
        if not any(value is not None for value in direct + dots):
            for key in (flat_dph, flat_dotph, total_dph, flat_dps, flat_dotps, total_dps): final[key] = None
            return
        final[flat_dph] = sum(float(value or 0) for value in direct)
        final[flat_dotph] = sum(float(value or 0) for value in dots)
        final[total_dph] = final[flat_dph] + final[flat_dotph]
        final[flat_dps] = final[flat_dph] * attack_rate
        final[flat_dotps] = final[flat_dotph] * attack_rate
        final[total_dps] = final[total_dph] * attack_rate

    fold_zone("flat_dph", "flat_dotph", "total_dph", "flat_dps", "flat_dotps", "total_dps")
    fold_zone("flat_weakpoint_dph", "flat_weakpoint_dotph", "total_weakpoint_dph", "flat_weakpoint_dps", "flat_weakpoint_dotps", "total_weakpoint_dps")
    fold_zone("flat_resistant_dph", "flat_resistant_dotph", "total_resistant_dph", "flat_resistant_dps", "flat_resistant_dotps", "total_resistant_dps")
    return final


def compute_attack_results(*, attacks: Mapping[str, Attack], selected: str, compute_attack: Callable[[str, Attack], AttackResult], attack_rate_for: Callable[[AttackResult], float]) -> dict[str, AttackResult]:
    needed = needed_attack_names(attacks, selected)
    results = {name: compute_attack(name, attacks[name]) for name in needed}
    for name, result in results.items():
        result.final = fold_attack_tree(result, list(walk_tree(name, results)), attack_rate=attack_rate_for(result))
    return results
