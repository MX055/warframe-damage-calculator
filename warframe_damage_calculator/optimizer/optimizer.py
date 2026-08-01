from __future__ import annotations

import math
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from itertools import combinations

from ..domain.enemies import Enemy
from ..domain.loadouts import Loadout
from ..domain.perks import ResolvedPerk
from ..domain.results import CalculationResult
from ..domain.upgrades import ResolvedEffect
from ..engine.calculator import Calculator
from ..engine.context import CalculationContext
from ..engine.perks import resolve_perks
from ..engine.weapon_calculator import WeaponCalculator
from .candidates import DEFAULT_UPGRADE_BLACKLIST, Candidate, CandidatePreparation
from .progress import ProgressCallback, _ProgressReporter, terminal_progress
from .rivens import DEFAULT_RIVEN_STAT_BLACKLIST, RivenCandidates
from .search import Search


Metric = Callable[[CalculationResult], float]


def _balanced_damage(direct: float, dot: float, balance_bonus: float = 0.1) -> float:
    direct = max(float(direct), 0.0)
    dot = max(float(dot), 0.0)
    total = direct + dot
    if total == 0: return 0.0
    balance = 2 * math.sqrt(direct * dot) / total
    return total * (1 + balance_bonus * balance)


def default_metric(result: CalculationResult) -> float:
    average = result.aggregate.average
    dps = _balanced_damage(average.direct_dps, average.dot_dps)
    dph = _balanced_damage(average.direct_dph, average.dot_dph)
    spatial = result.attacks[result.selected_attack].spatial
    damage_mass = spatial.damage_mass if spatial is not None else 1.0
    if dps <= 0 or dph <= 0 or damage_mass <= 0: return 0.0
    return (dps * dph * damage_mass) ** (1 / 3)


@dataclass(frozen=True, slots=True)
class Optimization:
    loadout: Loadout
    result: CalculationResult
    score: float
    evaluations: int
    resolutions: int
    attempts: int = 0
    cache_hits: int = 0
    approximations: int = 0
    elapsed: float = 0.0
    summary: dict[str, int | float | str | bool] | None = None


class Optimizer(Search, CandidatePreparation, RivenCandidates):
    __slots__ = ("calculator", "_priority_cache", "_component_id_cache", "_next_component_id", "_resolved_effect_cache", "_upgrade_effects_cache")

    def __init__(self, calculator: Calculator) -> None:
        if not isinstance(calculator, Calculator): raise TypeError("calculator must be a Calculator")
        self.calculator = calculator
        self._priority_cache: dict[tuple, tuple[float, int, str]] = {}
        self._component_id_cache: dict[int, tuple[object, int]] = {}
        self._next_component_id = 1
        self._resolved_effect_cache: dict[int, tuple[ResolvedEffect, ...]] = {}
        self._upgrade_effects_cache: dict[tuple[int, ...], tuple[ResolvedEffect, ...]] = {}

    def resolve(self, metric: Metric = default_metric, *, attack: str | None = None, body_part: str | None = None, evaluations: int = 20_000, riven: bool = True, evolutions: bool = True, upgrade_blacklist: Collection[str] | None = DEFAULT_UPGRADE_BLACKLIST, riven_stat_blacklist: Collection[str] | None = DEFAULT_RIVEN_STAT_BLACKLIST, progress: ProgressCallback | None = terminal_progress) -> Optimization:
        if not callable(metric): raise TypeError("metric must be callable")
        if evaluations < 1: raise ValueError("evaluations must be at least 1")
        if not isinstance(riven, bool): raise TypeError("riven must be a bool")
        if not isinstance(evolutions, bool): raise TypeError("evolutions must be a bool")
        if upgrade_blacklist is not None and (isinstance(upgrade_blacklist, (str, bytes)) or not isinstance(upgrade_blacklist, Collection)): raise TypeError("upgrade_blacklist must be a collection of upgrade names or None")
        if riven_stat_blacklist is not None and (isinstance(riven_stat_blacklist, (str, bytes)) or not isinstance(riven_stat_blacklist, Collection)): raise TypeError("riven_stat_blacklist must be a collection of stat names or None")
        if progress is not None and not callable(progress): raise TypeError("progress must be callable or None")
        started = time.perf_counter()
        resolution_budget = evaluations
        search_scale = max(0.25, math.sqrt(evaluations / 5_000))
        mode_scale = 2.0
        reporter = _ProgressReporter(progress, budget=evaluations)
        pools = self._candidate_pools(riven=riven, evolutions=evolutions, upgrade_blacklist=upgrade_blacklist, riven_stat_blacklist=riven_stat_blacklist, search_scale=search_scale)
        base = self._complete_fixed_loadout(self.calculator.loadout, evolutions=evolutions)
        selected_attack = attack or self.calculator.weapon.default_attack
        if selected_attack not in self.calculator.weapon.attacks: raise ValueError(f"unknown attack {selected_attack!r}")
        evaluator = Calculator(self.calculator.weapon, self.calculator.target, base)
        selected_bodypart, target = evaluator._select_bodypart(body_part)
        context = CalculationContext(weapon=evaluator.weapon, target=target if target is not None else Enemy(), attack=selected_attack, loadout=evaluator.loadout, resolved_perks=(), state=dict(evaluator.weapon.calculation_defaults))
        prepared_names = tuple(WeaponCalculator(context).collect_attack_tree())
        cache: dict[tuple, Candidate] = {}
        perk_cache: dict[tuple[int, ...], tuple[ResolvedPerk, ...]] = {}
        use_compact_metric = metric is default_metric
        evaluations_used = 0
        resolutions = 0
        attempts = 0
        cache_hits = 0

        def evaluate(loadout: Loadout) -> tuple[Candidate, bool]:
            nonlocal evaluations_used, resolutions, attempts, cache_hits
            attempts += 1
            key = self._loadout_key(loadout)
            cached = cache.get(key)
            if cached is not None:
                cache_hits += 1
                return cached, False
            if evaluations_used >= resolution_budget: return best, False
            score = 0.0
            representative: CalculationResult | None = None
            perk_key = tuple(self._component_id(perk) for perk in loadout.evolutions)
            resolved_perks = perk_cache.get(perk_key)
            if resolved_perks is None:
                resolved_perks = resolve_perks(self.calculator.weapon, loadout.evolutions, dict(self.calculator.weapon.calculation_defaults))
                perk_cache[perk_key] = resolved_perks
            prepared_upgrade_effects = self._compiled_upgrade_effects(loadout)
            evaluator.loadout = loadout
            if use_compact_metric:
                direct_dph, dot_dph, direct_dps, dot_dps, damage_mass = evaluator._calculate_metric_components(selected_attack, target, {}, resolved_perks=resolved_perks, prepared_names=prepared_names, prepared_upgrade_effects=prepared_upgrade_effects)
                dps = _balanced_damage(direct_dps, dot_dps)
                dph = _balanced_damage(direct_dph, dot_dph)
                score = (dps * dph * damage_mass) ** (1 / 3) if dps > 0 and dph > 0 and damage_mass > 0 else 0.0
            else:
                result = evaluator._calculate(selected_attack, selected_bodypart, target, {}, copy_inputs=False, resolved_perks=resolved_perks, validate=False, prepared_names=prepared_names, prepared_upgrade_effects=prepared_upgrade_effects)
                score = float(metric(result))
                representative = result
            if not math.isfinite(score): raise ValueError("metric must return a finite number")
            resolutions += 1
            candidate = Candidate(loadout, score, representative)
            cache[key] = candidate
            evaluations_used += 1
            reporter.record_evaluation(evaluations_used, resolutions=resolutions, attempts=attempts, cache_hits=cache_hits, best_score=max(best.score if "best" in locals() else float("-inf"), score))
            return candidate, True

        best = Candidate(base, float("-inf"))
        base_candidate, _ = evaluate(base)
        best = base_candidate
        pool = [best]
        pool_limit = min(32, max(4, round(6 * mode_scale * search_scale ** 0.35)))

        def retain(candidates: list[Candidate]) -> list[Candidate]:
            return self._select_diverse(candidates, pool_limit)

        seed_loadouts = list(self._seed_loadouts(base, pools, search_scale=search_scale))
        local_passes = min(4, max(1, round(2 * search_scale ** 0.35)))
        local_sources = min(pool_limit, max(2, round(2 * search_scale ** 0.5)))
        beam_sources = min(pool_limit, max(2, round(3 * search_scale ** 0.5)))
        cleanup_pass_limit = min(8, max(2, round(3 * search_scale ** 0.35)))
        estimated_total = resolution_budget
        reporter.set_estimated_total(max(estimated_total, 1))
        reporter.begin_phase("Seeds", min(len(seed_loadouts), resolution_budget - evaluations_used), completed=evaluations_used)
        seed_candidates: list[Candidate] = []
        for index, loadout in enumerate(seed_loadouts):
            reporter.update_plan(min(len(seed_loadouts) - index, resolution_budget - evaluations_used))
            if evaluations_used >= resolution_budget: break
            candidate, consumed = evaluate(loadout)
            if not consumed: continue
            if candidate.score > best.score: best = candidate
            seed_candidates.append(candidate)
        pool = retain([*pool, *seed_candidates, best])

        def change_group(origin: Loadout, candidate: Loadout) -> tuple[str, int]:
            for index, (left, right) in enumerate(zip(origin.mods, candidate.mods)):
                if left is not right: return "mod", index
            if len(origin.mods) != len(candidate.mods): return "mod", min(len(origin.mods), len(candidate.mods))
            for index, (left, right) in enumerate(zip(origin.arcanes, candidate.arcanes)):
                if left is not right: return "arcane", index
            if len(origin.arcanes) != len(candidate.arcanes): return "arcane", min(len(origin.arcanes), len(candidate.arcanes))
            origin_perks = {self.calculator.weapon.perks[perk].tier: perk for perk in origin.evolutions if perk in self.calculator.weapon.perks}
            candidate_perks = {self.calculator.weapon.perks[perk].tier: perk for perk in candidate.evolutions if perk in self.calculator.weapon.perks}
            for tier in sorted(origin_perks.keys() | candidate_perks.keys()):
                if origin_perks.get(tier) is not candidate_perks.get(tier): return "perk", tier
            return "progenitor", 0

        frontier: dict[tuple[str, int], Candidate] = {}
        local_deadline = max(evaluations_used, round(resolution_budget * 0.48))
        reporter.begin_phase("Local search", max(local_deadline - evaluations_used, 0), completed=evaluations_used)
        for source in list(pool)[:local_sources]:
            if evaluations_used >= local_deadline: break
            current = source
            for _ in range(local_passes):
                neighbors = list(self._exact_neighbors(current.loadout, pools))
                reporter.update_plan(min(len(neighbors), local_deadline - evaluations_used))
                improved = current
                pass_candidates: list[Candidate] = []
                for loadout in neighbors:
                    if evaluations_used >= local_deadline: break
                    candidate, consumed = evaluate(loadout)
                    if not consumed: continue
                    if candidate.score > improved.score: improved = candidate
                    pass_candidates.append(candidate)
                    group = change_group(current.loadout, candidate.loadout)
                    previous = frontier.get(group)
                    if candidate.score <= current.score and (previous is None or candidate.score > previous.score): frontier[group] = candidate
                pool = retain([*pool, *pass_candidates, improved, best])
                if improved.score <= current.score: break
                current = improved
                if current.score > best.score: best = current
            pool = retain([*pool, current, best])

        beam_deadline = max(evaluations_used, round(resolution_budget * 0.85))
        reporter.begin_phase("Perturbations", max(beam_deadline - evaluations_used, 0), completed=evaluations_used)
        beam_starts = sorted(frontier.values(), key=lambda candidate: candidate.score, reverse=True)[:beam_sources]
        for source in beam_starts:
            if evaluations_used >= beam_deadline: break
            candidates: list[Candidate] = []
            neighbors = list(self._exact_neighbors(source.loadout, pools))
            reporter.update_plan(min(len(neighbors), beam_deadline - evaluations_used))
            for loadout in neighbors:
                if evaluations_used >= beam_deadline: break
                candidate, consumed = evaluate(loadout)
                if not consumed: continue
                candidates.append(candidate)
                if candidate.score > best.score: best = candidate
            pool = retain([*pool, *candidates, best])

        rebuild_deadline = max(evaluations_used, round(resolution_budget * 0.95))
        reporter.begin_phase("Rebuilds", max(rebuild_deadline - evaluations_used, 0), completed=evaluations_used)
        rebuild_sources = [best, *[candidate for candidate in pool if candidate is not best]][:max(2, round(3 * search_scale ** 0.4))]
        for source_index, source in enumerate(rebuild_sources):
            if evaluations_used >= rebuild_deadline: break
            fixed_mods = len(base.mods)
            mutable = [index for index in range(fixed_mods, len(source.loadout.mods)) if source.loadout.mods[index].slot == "regular_mod" and not self._is_riven(source.loadout.mods[index])]
            pairs = list(combinations(mutable, 2))
            pair_limit = min(len(pairs), max(3, round(5 * search_scale ** 0.4)))
            pair_offset = source_index * pair_limit % max(len(pairs), 1)
            ordered_pairs = [*pairs[pair_offset:], *pairs[:pair_offset]]
            for first, second in ordered_pairs[:pair_limit]:
                if evaluations_used >= rebuild_deadline: break
                mods = [mod for index, mod in enumerate(source.loadout.mods) if index not in {first, second}]
                current = self._loadout(mods=mods, arcanes=source.loadout.arcanes, evolutions=source.loadout.evolutions, progenitor=source.loadout.progenitor)
                current_candidate, _ = evaluate(current)
                for _ in range(2):
                    selected = {mod.name for mod in current.mods}
                    improved = current_candidate
                    for mod in pools["mods"]:
                        if evaluations_used >= rebuild_deadline: break
                        if mod.slot != "regular_mod" or mod.name in selected: continue
                        candidate_loadout = self._loadout(mods=[*current.mods, mod], arcanes=current.arcanes, evolutions=current.evolutions, progenitor=current.progenitor)
                        if not self._legal(candidate_loadout): continue
                        candidate, _ = evaluate(candidate_loadout)
                        if candidate.score > improved.score: improved = candidate
                    if improved.score <= current_candidate.score: break
                    current_candidate = improved
                    current = improved.loadout
                if current_candidate.score > best.score: best = current_candidate
                pool = retain([*pool, current_candidate, best])

        cleanup_passes = 0
        reporter.begin_phase("Cleanup", max(resolution_budget - evaluations_used, 0), completed=evaluations_used)
        while evaluations_used < resolution_budget and cleanup_passes < cleanup_pass_limit:
            cleanup_passes += 1
            origin = best
            improved = origin
            neighbors = list(self._exact_neighbors(origin.loadout, pools))
            reporter.update_plan(min(len(neighbors), resolution_budget - evaluations_used))
            for loadout in neighbors:
                if evaluations_used >= resolution_budget: break
                candidate, _ = evaluate(loadout)
                if candidate.score > improved.score: improved = candidate
            if improved.score <= origin.score: break
            best = improved

        elapsed = time.perf_counter() - started
        reporter.close(completed=evaluations_used, resolutions=resolutions, attempts=attempts, cache_hits=cache_hits, best_score=best.score)
        summary = {
            "converged": evaluations_used < resolution_budget,
            "budget_exhausted": evaluations_used >= resolution_budget,
            "score": best.score,
            "elapsed": elapsed,
            "evaluations": evaluations_used,
            "evaluation_budget": evaluations,
            "resolutions": resolutions,
            "resolution_budget": resolution_budget,
            "attempts": attempts,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / attempts if attempts else 0.0,
        }
        result = best.result
        if result is None:
            evaluator.loadout = best.loadout
            perk_key = tuple(self._component_id(perk) for perk in best.loadout.evolutions)
            resolved_perks = perk_cache.get(perk_key)
            if resolved_perks is None:
                resolved_perks = resolve_perks(self.calculator.weapon, best.loadout.evolutions, dict(self.calculator.weapon.calculation_defaults))
            result = evaluator._calculate(selected_attack, selected_bodypart, target, {}, copy_inputs=False, resolved_perks=resolved_perks, validate=False, prepared_names=prepared_names, prepared_upgrade_effects=self._compiled_upgrade_effects(best.loadout))
        return Optimization(best.loadout.copy(), result, best.score, evaluations_used, resolutions, attempts, cache_hits, 0, elapsed, summary)
