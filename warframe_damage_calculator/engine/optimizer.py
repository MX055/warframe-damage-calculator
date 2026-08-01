from __future__ import annotations

import heapq
import math
import random
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Collection, Iterator, Mapping
from dataclasses import dataclass
from itertools import combinations, permutations, product

from ..database.arsenal import arsenal
from ..domain.enemies import Enemy
from ..domain.loadouts import Loadout, Progenitor
from ..domain.results import CalculationResult
from ..domain.upgrades import Arcane, Mod, Perk, ResolvedEffect, ResolvedPerk, UpgradeStats
from .calculator import Calculator, _resolve_perks
from .context import CalculationContext
from .weapon_calculator import WeaponCalculator

Metric = Callable[[CalculationResult], float]

RIVEN_ROLLS = ((2, 0, 0.99, 0.0), (2, 1, 1.2375, -0.495), (3, 0, 0.75, 0.0), (3, 1, 0.9375, -0.75))
RIVEN_NON_NEGATIVE = frozenset({"cold", "electricity", "heat", "punch_through", "toxin"})
RIVEN_RELEVANT = frozenset({"damage_bonus", "cold", "crit_chance", "crit_damage", "corpus_damage", "electricity", "fire_rate", "grineer_damage", "heat", "impact", "infested_damage", "magazine_capacity", "multishot", "punch_through", "puncture", "reload_speed", "slash", "status_chance", "status_duration", "toxin"})
FACTION_DAMAGE_STATS = frozenset({"corpus_damage", "corrupted_damage", "grineer_damage", "infested_damage"})
DEFAULT_RIVEN_STAT_BLACKLIST = FACTION_DAMAGE_STATS
DEFAULT_UPGRADE_BLACKLIST = frozenset({
    "Aero Agility", "Aero Periphery", "Air Recon", "Akimbo Slip Shot", "Avenging Truth", "Broad Eye", "Cascadia Accuracy", "Cascadia Overcharge", "Catalyzer Link", "Combo Fury", "Combo Killer", "Deadly Maneuvers", "Dreadful Killshot", "Embedded Catalyzer", "Exodia Contagion", "Exodia Epidemic", "Fractalized Reset", "Hunter Synergy", "Mark of the Beast", "Mecha Overdrive", "Melee Assimilation", "Melee Careen", "Melee Exposure", "Melee Retaliation", "Mortal Conduct", "Nano-Applicator", "Necrophagic Vigor", "Overview", "Pax Soar", "Primary Bulwark", "Primary Dexterity", "Primary Overcharge", "Proton Jet", "Proton Snap", "Secondary Dexterity", "Secondary Kinship", "Secondary Outburst", "Secondary Surge", "Soaring Strike", "Spectral Serration", "Zazvat-Kar",
})


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
class OptimizationProgress:
    stage: str
    fraction: float
    stage_fraction: float
    elapsed: float
    eta: float | None
    evaluations: int
    evaluation_budget: int
    resolutions: int
    attempts: int
    cache_hits: int
    cache_hit_rate: float
    best_score: float
    complete: bool


ProgressCallback = Callable[[OptimizationProgress], None]


class _TerminalProgress:
    __slots__ = ("_lock", "_last_length")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_length = 0

    def __call__(self, progress: OptimizationProgress) -> None:
        with self._lock:
            width = 30
            filled = width if progress.complete else min(width - 1, int(progress.fraction * width))
            bar = "█" * filled + "·" * (width - filled)
            label = "Complete" if progress.complete else "Optimizing"
            message = f"{label} {bar} {progress.fraction:6.2%} · {progress.elapsed:,.1f}s elapsed"
            if not progress.complete:
                message += " · estimating ETA" if progress.eta is None else f" · {progress.eta:,.1f}s ETA"
            padding = " " * max(0, self._last_length - len(message))
            print(f"\r{message}{padding}", end="\n" if progress.complete else "", file=sys.stdout, flush=True)
            self._last_length = 0 if progress.complete else len(message)


terminal_progress: ProgressCallback = _TerminalProgress()


@dataclass(slots=True)
class _ProgressState:
    completed: int = 0
    estimated_total: int = 1
    stage: str = "Seeds"
    stage_started: int = 0
    stage_total: int = 1
    resolutions: int = 0
    attempts: int = 0
    cache_hits: int = 0
    best_score: float = 0.0
    complete: bool = False


class _ProgressReporter:
    __slots__ = ("_callback", "_started", "_interval", "_budget", "_state", "_lock", "_publish_lock", "_stop", "_thread", "_progress", "_samples", "_display_eta", "_error")

    def __init__(self, callback: ProgressCallback | None, *, budget: int, interval: float = 0.1) -> None:
        self._callback = callback
        self._started = time.perf_counter()
        self._interval = interval
        self._budget = budget
        self._state = _ProgressState()
        self._lock = threading.Lock()
        self._publish_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="optimizer-progress", daemon=True) if callback is not None else None
        self._progress = 0.0
        self._samples: deque[tuple[float, int]] = deque(maxlen=64)
        self._samples.append((self._started, 0))
        self._display_eta: float | None = None
        self._error: BaseException | None = None
        if self._thread is not None: self._thread.start()

    def set_estimated_total(self, estimated_total: int) -> None:
        if self._callback is None: return
        self._check_error()
        with self._lock:
            self._state.estimated_total = max(int(estimated_total), self._state.completed + 1, 1)

    def begin_phase(self, stage: str, planned: int, *, completed: int) -> None:
        if self._callback is None: return
        self._check_error()
        with self._lock:
            self._state.completed = completed
            self._state.stage = stage
            self._state.stage_started = completed
            self._state.stage_total = max(int(planned), 1)
        self._publish()

    def update_plan(self, planned_remaining: int) -> None:
        if self._callback is None: return
        self._check_error()
        with self._lock:
            stage_done = max(self._state.completed - self._state.stage_started, 0)
            self._state.stage_total = max(stage_done + int(planned_remaining), stage_done + 1, 1)

    def record_evaluation(self, completed: int, *, resolutions: int, attempts: int, cache_hits: int, best_score: float) -> None:
        if self._callback is None: return
        self._check_error()
        now = time.perf_counter()
        with self._lock:
            self._state.completed = completed
            self._state.resolutions = resolutions
            self._state.attempts = attempts
            self._state.cache_hits = cache_hits
            self._state.best_score = max(self._state.best_score, best_score)
            self._samples.append((now, completed))

    def close(self, *, completed: int, resolutions: int, attempts: int, cache_hits: int, best_score: float) -> None:
        if self._callback is None: return
        with self._lock:
            self._state.completed = completed
            self._state.resolutions = resolutions
            self._state.attempts = attempts
            self._state.cache_hits = cache_hits
            self._state.best_score = max(self._state.best_score, best_score)
            self._state.complete = True
            self._progress = 1.0
        self._stop.set()
        assert self._thread is not None
        self._thread.join()
        self._check_error()
        self._publish()
        self._check_error()

    def _run(self) -> None:
        self._publish()
        while not self._stop.wait(self._interval): self._publish()

    def _check_error(self) -> None:
        if self._error is not None: raise RuntimeError("progress callback failed") from self._error

    def _eta(self, completed: int, estimated_total: int) -> float | None:
        with self._lock: samples = tuple(self._samples)
        remaining = max(estimated_total - completed, 0)
        if completed < 16 or len(samples) < 2: return None
        first_time, first_count = samples[0]
        last_time, last_count = samples[-1]
        recent_completed = last_count - first_count
        recent_elapsed = last_time - first_time
        total_elapsed = last_time - self._started
        if recent_completed <= 0 or recent_elapsed <= 0 or completed <= 0: return None
        recent_seconds = recent_elapsed / recent_completed
        overall_seconds = total_elapsed / completed
        eta = max(remaining * (0.65 * recent_seconds + 0.35 * overall_seconds), 0.1)
        if self._display_eta is None: self._display_eta = eta
        else:
            alpha = 0.12 if eta < self._display_eta else 0.25
            self._display_eta = alpha * eta + (1 - alpha) * self._display_eta
        return self._display_eta

    def _fractions(self, state: _ProgressState) -> tuple[float, float]:
        weights = {"Seeds": 0.12, "Local search": 0.53, "Perturbations": 0.20, "Cleanup": 0.15}
        order = ("Seeds", "Local search", "Perturbations", "Cleanup")
        stage_done = max(state.completed - state.stage_started, 0)
        stage_fraction = min(stage_done / max(state.stage_total, 1), 1.0)
        try: index = order.index(state.stage)
        except ValueError: return self._progress, stage_fraction
        estimated = min(sum(weights[name] for name in order[:index]) + weights[state.stage] * min(stage_fraction, 0.95), 0.985)
        self._progress = min(max(self._progress, estimated), 0.985)
        return self._progress, stage_fraction

    def _publish(self) -> None:
        if self._callback is None or self._error is not None: return
        with self._publish_lock:
            try:
                with self._lock:
                    state = _ProgressState(**{field: getattr(self._state, field) for field in _ProgressState.__dataclass_fields__})
                elapsed = time.perf_counter() - self._started
                fraction, stage_fraction = (1.0, 1.0) if state.complete else self._fractions(state)
                eta = None if state.complete else self._eta(state.completed, state.estimated_total)
                snapshot = OptimizationProgress(
                    stage="Complete" if state.complete else state.stage,
                    fraction=fraction,
                    stage_fraction=stage_fraction,
                    elapsed=elapsed,
                    eta=eta,
                    evaluations=state.completed,
                    evaluation_budget=self._budget,
                    resolutions=state.resolutions,
                    attempts=state.attempts,
                    cache_hits=state.cache_hits,
                    cache_hit_rate=state.cache_hits / state.attempts if state.attempts else 0.0,
                    best_score=state.best_score,
                    complete=state.complete,
                )
                self._callback(snapshot)
            except BaseException as error:
                self._error = error
                self._stop.set()


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


@dataclass(frozen=True, slots=True)
class _Candidate:
    loadout: Loadout
    score: float
    result: CalculationResult | None = None


class Optimizer:
    __slots__ = ("calculator", "_priority_cache", "_component_id_cache", "_next_component_id", "_resolved_effect_cache", "_upgrade_effects_cache")

    def __init__(self, calculator: Calculator) -> None:
        if not isinstance(calculator, Calculator): raise TypeError("calculator must be a Calculator")
        self.calculator = calculator
        self._priority_cache: dict[tuple, tuple[float, int, str]] = {}
        self._component_id_cache: dict[int, tuple[object, int]] = {}
        self._next_component_id = 1
        self._resolved_effect_cache: dict[int, tuple[ResolvedEffect, ...]] = {}
        self._upgrade_effects_cache: dict[tuple[int, ...], tuple[ResolvedEffect, ...]] = {}

    def resolve(self, metric: Metric = default_metric, *, attack: str | None = None, body_part: str | None = None, evaluations: int = 20_000, riven: bool = True, evolutions: bool = True, upgrade_blacklist: Collection[str] | None = None, riven_stat_blacklist: Collection[str] | None = None, progress: ProgressCallback | None = terminal_progress) -> Optimization:
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
        cache: dict[tuple, _Candidate] = {}
        perk_cache: dict[tuple[int, ...], tuple[ResolvedPerk, ...]] = {}
        use_compact_metric = metric is default_metric
        evaluations_used = 0
        resolutions = 0
        attempts = 0
        cache_hits = 0

        def evaluate(loadout: Loadout) -> tuple[_Candidate, bool]:
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
                resolved_perks = _resolve_perks(self.calculator.weapon, loadout.evolutions, dict(self.calculator.weapon.calculation_defaults))
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
            candidate = _Candidate(loadout, score, representative)
            cache[key] = candidate
            evaluations_used += 1
            reporter.record_evaluation(evaluations_used, resolutions=resolutions, attempts=attempts, cache_hits=cache_hits, best_score=max(best.score if "best" in locals() else float("-inf"), score))
            return candidate, True

        best = _Candidate(base, float("-inf"))
        base_candidate, _ = evaluate(base)
        best = base_candidate
        pool = [best]
        pool_limit = min(32, max(4, round(6 * mode_scale * search_scale ** 0.35)))

        def retain(candidates: list[_Candidate]) -> list[_Candidate]:
            return self._select_diverse(candidates, pool_limit)

        seed_loadouts = list(self._seed_loadouts(base, pools, search_scale=search_scale))
        local_passes = min(10, max(2, round(3 * mode_scale ** 0.5 * search_scale ** 0.45)))
        neighbor_limit = min(1_024, max(48, round(160 * mode_scale * search_scale)))
        perturbation_limit = min(8_192, max(128, round(512 * mode_scale * search_scale)))
        perturbation_sources = min(20, max(2, round(3 * mode_scale * search_scale ** 0.4)))
        cleanup_limit = min(96, max(12, round(16 * mode_scale * search_scale ** 0.6)))
        cleanup_pass_limit = min(12, max(3, round(4 * mode_scale ** 0.5 * search_scale ** 0.35)))
        estimated_total = min(resolution_budget, len(seed_loadouts) + pool_limit * local_passes * neighbor_limit + perturbation_limit + cleanup_limit * cleanup_pass_limit)
        reporter.set_estimated_total(max(estimated_total, 1))
        reporter.begin_phase("Seeds", min(len(seed_loadouts), resolution_budget - evaluations_used), completed=evaluations_used)
        seed_candidates: list[_Candidate] = []
        for index, loadout in enumerate(seed_loadouts):
            reporter.update_plan(min(len(seed_loadouts) - index, resolution_budget - evaluations_used))
            if evaluations_used >= resolution_budget: break
            candidate, consumed = evaluate(loadout)
            if not consumed: continue
            if candidate.score > best.score: best = candidate
            seed_candidates.append(candidate)
        pool = retain([*pool, *seed_candidates, best])

        reporter.begin_phase("Local search", max(resolution_budget - evaluations_used, 0), completed=evaluations_used)
        for source_index, source in enumerate(list(pool)):
            if evaluations_used >= resolution_budget: break
            current = source
            for _ in range(local_passes):
                neighbors = sorted(self._exact_neighbors(current.loadout, pools), key=self._estimate_loadout, reverse=True)
                reporter.update_plan(min(neighbor_limit, len(neighbors), resolution_budget - evaluations_used))
                improved = current
                checked = 0
                pass_candidates: list[_Candidate] = []
                for loadout in neighbors:
                    if evaluations_used >= resolution_budget or checked >= neighbor_limit: break
                    candidate, consumed = evaluate(loadout)
                    if not consumed: continue
                    checked += 1
                    if candidate.score > improved.score: improved = candidate
                    pass_candidates.append(candidate)
                pool = retain([*pool, *pass_candidates, improved, best])
                if improved.score <= current.score: break
                current = improved
                if current.score > best.score: best = current
            pool = retain([*pool, current, best])

        if evaluations_used < resolution_budget:
            generated: dict[tuple, Loadout] = {}
            for candidate in pool[:perturbation_sources]:
                for loadout in self._exact_perturbations(candidate.loadout, pools, search_scale=search_scale):
                    generated.setdefault(self._loadout_key(loadout), loadout)
                    if len(generated) >= perturbation_limit: break
            perturbations = sorted(generated.values(), key=self._estimate_loadout, reverse=True)
            reporter.begin_phase("Perturbations", min(len(perturbations), resolution_budget - evaluations_used), completed=evaluations_used)
            perturbation_candidates: list[_Candidate] = []
            for index, loadout in enumerate(perturbations):
                reporter.update_plan(min(len(perturbations) - index, resolution_budget - evaluations_used))
                if evaluations_used >= resolution_budget: break
                candidate, consumed = evaluate(loadout)
                if not consumed: continue
                if candidate.score > best.score: best = candidate
                perturbation_candidates.append(candidate)
            pool = retain([*pool, *perturbation_candidates, best])

        cleanup_passes = 0
        reporter.begin_phase("Cleanup", max(resolution_budget - evaluations_used, 0), completed=evaluations_used)
        while evaluations_used < resolution_budget and cleanup_passes < cleanup_pass_limit:
            cleanup_passes += 1
            improved = best
            removals = list(self._cleanup_removals(best.loadout))
            reporter.update_plan(min(len(removals), resolution_budget - evaluations_used))
            for _, loadout in removals:
                if evaluations_used >= resolution_budget: break
                candidate, _ = evaluate(loadout)
                if candidate.score > improved.score: improved = candidate
            weak_indices = []
            removal_scores = []
            for index, loadout in self._cleanup_removals(best.loadout):
                cached = cache.get(self._loadout_key(loadout))
                if cached is not None: removal_scores.append((best.score - cached.score, index))
            weak_indices = [index for _, index in sorted(removal_scores)[:8]]
            replacements = list(self._cleanup_replacements(best.loadout, pools, weak_indices, limit=cleanup_limit))
            reporter.update_plan(min(len(replacements), resolution_budget - evaluations_used))
            for loadout in replacements:
                if evaluations_used >= resolution_budget: break
                candidate, _ = evaluate(loadout)
                if candidate.score > improved.score: improved = candidate
            if improved.score <= best.score: break
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
                resolved_perks = _resolve_perks(self.calculator.weapon, best.loadout.evolutions, dict(self.calculator.weapon.calculation_defaults))
            result = evaluator._calculate(selected_attack, selected_bodypart, target, {}, copy_inputs=False, resolved_perks=resolved_perks, validate=False, prepared_names=prepared_names, prepared_upgrade_effects=self._compiled_upgrade_effects(best.loadout))
        return Optimization(best.loadout.copy(), result, best.score, evaluations_used, resolutions, attempts, cache_hits, 0, elapsed, summary)

    def _loadout(self, *, mods=(), arcanes=(), evolutions=(), progenitor=None) -> Loadout:
        return Loadout._from_parts(mods=mods, arcanes=arcanes, evolutions=evolutions, progenitor=progenitor)

    def _candidate_pools(self, *, riven: bool = True, evolutions: bool = True, upgrade_blacklist: Collection[str] | None = None, riven_stat_blacklist: Collection[str] | None = None, search_scale: float = 1.0) -> dict[str, tuple]:
        use_default_upgrade_blacklist = upgrade_blacklist is None
        upgrade_blacklist = frozenset(name.casefold() for name in (DEFAULT_UPGRADE_BLACKLIST if upgrade_blacklist is None else map(str, upgrade_blacklist)))
        riven_stat_blacklist = frozenset(DEFAULT_RIVEN_STAT_BLACKLIST if riven_stat_blacklist is None else map(str, riven_stat_blacklist))
        weapon = self.calculator.weapon
        compatible_mods = tuple(mod for mod in arsenal.mod.filter(weapon=weapon, implemented=True) if mod.name.casefold() not in upgrade_blacklist and not (use_default_upgrade_blacklist and self._has_faction_damage(mod)))
        mod_limit = min(192, max(36, round(108 * search_scale ** 0.4)))
        regular_mods = self._prepare_pool(compatible_mods, mod_limit)
        locked_riven = any(self._is_riven(mod) for mod in self.calculator.loadout.mods)
        riven_limit = min(192, max(16, round(64 * search_scale ** 0.5)))
        rivens = () if locked_riven or not riven else self._riven_candidates(limit=riven_limit, stat_blacklist=riven_stat_blacklist)
        mods = (*regular_mods, *rivens)
        compatible_arcanes = tuple(arcane for arcane in arsenal.arcane.filter(weapon=weapon, implemented=True) if arcane.name.casefold() not in upgrade_blacklist and not (use_default_upgrade_blacklist and self._has_faction_damage(arcane)))
        arcane_limit = min(96, max(18, round(54 * search_scale ** 0.4)))
        arcanes = self._prepare_pool(compatible_arcanes, arcane_limit)
        perks = {tier: implemented for tier, choices in weapon.perk_choices.items() if evolutions and (implemented := tuple(perk for perk in choices.values() if perk.implemented and perk.name.casefold() not in upgrade_blacklist and not (use_default_upgrade_blacklist and self._has_faction_damage(perk))))}
        progenitors = tuple(Progenitor(element, 0.6) for element in ("impact", "heat", "cold", "electricity", "toxin", "magnetic", "radiation")) if "progenitor" in weapon.traits else ()
        return {"mods": mods, "arcanes": arcanes, "perks": perks, "progenitors": progenitors, "rivens": rivens}

    def _has_faction_damage(self, upgrade: Mod | Arcane | Perk) -> bool:
        return bool(FACTION_DAMAGE_STATS.intersection(upgrade.stats))

    def _riven_candidates(self, *, limit: int = 32, stat_blacklist: Collection[str] = ()) -> tuple[Mod, ...]:
        category = self._riven_category()
        if category is None or self.calculator.weapon.disposition <= 0: return ()
        base_stats = arsenal.database.get("riven_stats", {}).get(category, {})
        if not base_stats: return ()
        positive_stats = [stat for stat in base_stats if stat in RIVEN_RELEVANT and stat not in stat_blacklist]
        positive_stats.sort(key=lambda stat: self._riven_stat_priority(stat, float(base_stats[stat])), reverse=True)
        positive_stats = positive_stats[:14 if limit > 32 else 10]
        negative_stats = [stat for stat in base_stats if stat not in RIVEN_NON_NEGATIVE and stat not in stat_blacklist]
        negative_stats.sort(key=lambda stat: self._riven_negative_priority(stat, float(base_stats[stat])))
        negative_stats = negative_stats[:10 if limit > 32 else 6]
        candidates: dict[str, Mod] = {}
        disposition = float(self.calculator.weapon.disposition)
        from itertools import combinations
        for positive_count, negative_count, positive_factor, negative_factor in RIVEN_ROLLS:
            for positives in combinations(positive_stats, positive_count):
                negatives = (None,) if negative_count == 0 else tuple(stat for stat in negative_stats if stat not in positives)
                for negative in negatives:
                    fields = {stat: float(base_stats[stat]) * disposition * positive_factor * 1.1 for stat in positives}
                    if negative is not None: fields[negative] = float(base_stats[negative]) * disposition * negative_factor * 0.9
                    name = self._riven_name(fields)
                    candidates[name] = Mod(name=name, stats=UpgradeStats(**fields))
        ranked = sorted(candidates.values(), key=self._upgrade_priority, reverse=True)
        return tuple(ranked[:limit])

    def _riven_category(self) -> str | None:
        weapon = self.calculator.weapon
        if weapon.type == "melee": return "melee"
        if weapon.type == "secondary": return "pistol"
        if weapon.type == "archgun": return "archgun"
        if weapon.type == "primary": return "shotgun" if weapon.subtype == "shotgun" else "rifle"
        return None

    def _riven_stat_priority(self, stat: str, value: float) -> tuple[float, float, str]:
        mod = Mod(name=f"Riven {stat}", stats=UpgradeStats(**{stat: value * max(float(self.calculator.weapon.disposition), 0.0)}))
        priority, _, _ = self._upgrade_priority(mod)
        preferred = 1.0 if stat in {"damage_bonus", "multishot", "crit_chance", "crit_damage", "status_chance", "fire_rate", "reload_speed", "cold", "electricity", "heat", "toxin"} else 0.0
        return preferred, priority, stat

    def _riven_negative_priority(self, stat: str, value: float) -> tuple[int, float, str]:
        harmless = stat in {"ammo_maximum", "projectile_speed", "recoil", "zoom"}
        return (0 if harmless else 1), abs(value), stat

    def _riven_name(self, fields: Mapping[str, float]) -> str:
        parts = [f"{stat}={value:+.6g}" for stat, value in sorted(fields.items())]
        return "Riven (" + ", ".join(parts) + ")"

    def _is_riven(self, mod: Mod) -> bool:
        return mod.name.casefold() == "riven" or mod.name.casefold().startswith("riven (")

    def _prepare_pool(self, pool: tuple, limit: int) -> tuple:
        ranked = sorted(pool, key=self._upgrade_priority, reverse=True)
        selected: list = []
        seen: set[str] = set()
        per_stat: dict[str, int] = {}
        for upgrade in ranked:
            stats = tuple(upgrade.stats)
            if any(per_stat.get(stat, 0) < 3 for stat in stats) or len(selected) < limit // 2:
                selected.append(upgrade)
                seen.add(upgrade.name)
                for stat in stats: per_stat[stat] = per_stat.get(stat, 0) + 1
            if len(selected) >= limit: break
        if len(selected) < limit:
            selected.extend(upgrade for upgrade in ranked if upgrade.name not in seen)
        return tuple(selected[:limit])

    def _upgrade_priority(self, upgrade: Mod | Arcane) -> tuple[float, int, str]:
        runtime = tuple(sorted(upgrade.runtime.as_dict().items()))
        key = (type(upgrade), upgrade.name, upgrade.slot, runtime)
        cached = self._priority_cache.get(key)
        if cached is not None: return cached
        relevant = {"damage_bonus", "base_damage", "multiplicative_base_damage", "multishot", "crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage", "status_chance", "status_damage", "fire_rate", "multiplicative_fire_rate", "attack_speed", "weakpoint_damage", "weakpoint_crit_chance", "reload_speed", "magazine_capacity", "ammo_efficiency", "impact", "puncture", "slash", "cold", "electricity", "heat", "toxin", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "void"}
        score = 0.0
        special = 0
        for stat, effects in upgrade.stats.items():
            if stat in relevant: score += 1.0
            for effect in effects:
                if isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool): score += min(abs(float(effect.value)), 10.0)
                if effect.automatic: special += 1
        priority = score + special * 4.0, len(upgrade.stats), upgrade.name
        self._priority_cache[key] = priority
        return priority

    def _estimate_loadout(self, loadout: Loadout) -> float:
        score = 0.0
        for upgrade in loadout.ranked_upgrades:
            priority, stat_count, _ = self._upgrade_priority(upgrade)
            score += priority + stat_count * 0.25
        score += len(loadout.evolutions) * 12.0
        if loadout.progenitor is not None: score += 8.0 + loadout.progenitor.bonus * 10.0
        names = {upgrade.name for upgrade in loadout.ranked_upgrades}
        elemental = sum(name in names for name in ("heat", "cold", "electricity", "toxin"))
        return score + elemental * 2.0

    def _open_slots(self, loadout: Loadout, pools: dict[str, tuple]) -> int:
        mod_slots = 8 + (1 if any(mod.slot == "exilus_mod" for mod in pools["mods"]) else 0) + (1 if self.calculator.weapon.type == "melee" and any(mod.slot == "stance_mod" for mod in pools["mods"]) else 0)
        occupied_tiers = {self.calculator.weapon.perks[perk].tier for perk in loadout.evolutions if perk in self.calculator.weapon.perks}
        return max(0, mod_slots - len(loadout.mods)) + max(0, 1 - len(loadout.arcanes)) + sum(tier not in occupied_tiers for tier in pools["perks"]) + int(loadout.progenitor is None and bool(pools["progenitors"]))

    def _complete_fixed_loadout(self, source: Loadout, *, evolutions: bool = True) -> Loadout:
        perks = list(source.evolutions)
        if evolutions:
            occupied = {self.calculator.weapon.perks[perk].tier for perk in perks if perk in self.calculator.weapon.perks}
            for tier, choices in self.calculator.weapon.perk_choices.items():
                implemented = tuple(perk for perk in choices.values() if perk.implemented)
                if tier not in occupied and len(implemented) == 1: perks.extend(implemented)
        return self._loadout(mods=source.mods, arcanes=source.arcanes, evolutions=perks, progenitor=source.progenitor)

    def _neighbors(self, loadout: Loadout, pools: dict[str, tuple], rng: random.Random):
        fixed = self.calculator.loadout
        mod_slots = 8 + (1 if any(mod.slot == "exilus_mod" for mod in pools["mods"]) else 0) + (1 if self.calculator.weapon.type == "melee" and any(mod.slot == "stance_mod" for mod in pools["mods"]) else 0)
        arcane_slots = 1
        if len(loadout.mods) < mod_slots:
            selected = {mod.name for mod in loadout.mods}
            for mod in self._shortlist(pools["mods"], selected, 36):
                candidate = self._loadout(mods=[*loadout.mods, mod], arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                if self._legal(candidate): yield candidate
        if len(loadout.arcanes) < arcane_slots:
            selected = {arcane.name for arcane in loadout.arcanes}
            for arcane in self._shortlist(pools["arcanes"], selected, 24):
                candidate = self._loadout(mods=loadout.mods, arcanes=[*loadout.arcanes, arcane], evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                if self._legal(candidate): yield candidate
        fixed_mods = len(fixed.mods)
        for index in range(fixed_mods, len(loadout.mods)):
            selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
            for mod in self._shortlist(pools["mods"], selected, 12):
                mods = list(loadout.mods)
                mods[index] = mod
                candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                if self._legal(candidate): yield candidate
        occupied = {self.calculator.weapon.perks[perk].tier for perk in loadout.evolutions if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in occupied: continue
            for perk in choices: yield self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=[*loadout.evolutions, perk], progenitor=loadout.progenitor)
        if fixed.progenitor is None:
            for progenitor in pools["progenitors"]:
                if progenitor != loadout.progenitor: yield self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=progenitor)
        if len(loadout.mods) >= mod_slots and len(loadout.mods) > fixed_mods:
            indices = list(range(fixed_mods, len(loadout.mods)))
            rng.shuffle(indices)
            for index in indices[:4]:
                mods = list(loadout.mods)
                mods.pop(index)
                yield self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)


    def _seed_loadouts(self, base: Loadout, pools: dict[str, tuple], *, search_scale: float = 1.0):
        profiles = (
            {"damage_bonus", "base_damage", "multiplicative_base_damage", "multishot"},
            {"crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage"},
            {"status_chance", "status_damage", "multishot"},
            {"fire_rate", "multiplicative_fire_rate", "attack_speed", "reload_speed", "magazine_capacity"},
            {"multishot", "crit_chance", "crit_damage"},
            {"multishot", "status_chance", "status_damage"},
            {"damage_bonus", "base_damage", "heat", "cold", "electricity", "toxin"},
            {"crit_chance", "crit_damage", "heat", "cold", "electricity", "toxin"},
            {"status_chance", "status_damage", "heat", "cold", "electricity", "toxin"},
            set(),
        )
        profiles = (*profiles,
                {"damage_bonus", "multishot", "crit_chance", "crit_damage", "status_chance", "status_damage"},
                {"multishot", "fire_rate", "reload_speed", "magazine_capacity"},
                {"damage_bonus", "multishot", "heat", "cold", "electricity", "toxin"},
                {"crit_chance", "crit_damage", "status_chance", "status_damage"},
                {"weakpoint_damage", "weakpoint_crit_chance", "crit_chance", "crit_damage"},
            )
        perk_limit = min(128, max(8, round(64 * search_scale ** 0.5)))
        perk_sets = self._perk_sets(base, pools, perk_limit)
        progenitors = (base.progenitor,) if base.progenitor is not None else (pools["progenitors"] or (None,))
        arcane_seed_limit = min(len(pools["arcanes"]), max(4, round(48 * search_scale ** 0.5)))
        arcanes = tuple(base.arcanes) if base.arcanes else (None, *pools["arcanes"][:arcane_seed_limit])
        seen: set[tuple] = set()
        for profile in profiles:
            mods = self._profile_mods(base, pools["mods"], profile)
            profile_perk_limit = min(len(perk_sets), max(2, round(8 * search_scale ** 0.35)))
            for perks in perk_sets[:profile_perk_limit]:
                for progenitor in progenitors:
                    profile_arcane_limit = min(len(arcanes), max(2, round(16 * search_scale ** 0.35)))
                    for arcane in arcanes[:profile_arcane_limit]:
                        arcanes_value = list(base.arcanes) if base.arcanes else ([] if arcane is None else [arcane])
                        candidate = self._loadout(mods=mods, arcanes=arcanes_value, evolutions=perks, progenitor=progenitor)
                        key = self._loadout_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate
        if not any(self._is_riven(mod) for mod in base.mods):
            riven_seed_limit = min(len(pools.get("rivens", ())), max(4, round(32 * search_scale ** 0.5)))
            for riven in pools.get("rivens", ())[:riven_seed_limit]:
                mods = self._profile_mods(base, tuple(mod for mod in pools["mods"] if not self._is_riven(mod)), set())
                regular_indices = [index for index, mod in enumerate(mods) if mod.slot == "regular_mod" and index >= len(base.mods)]
                if regular_indices:
                    mods[regular_indices[-1]] = riven
                elif sum(mod.slot == "regular_mod" for mod in mods) < 8:
                    mods.append(riven)
                candidate = self._loadout(mods=mods, arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        for perks in perk_sets:
            candidate = self._loadout(mods=self._profile_mods(base, pools["mods"], set()), arcanes=base.arcanes, evolutions=perks, progenitor=base.progenitor)
            key = self._loadout_key(candidate)
            if key not in seen and self._legal(candidate):
                seen.add(key)
                yield candidate

    def _profile_mods(self, base: Loadout, pool: tuple, profile: set[str]) -> list[Mod]:
        mods = list(base.mods)
        selected = {mod.name for mod in mods}
        ranked = sorted((mod for mod in pool if mod.name not in selected), key=lambda mod: self._profile_priority(mod, profile), reverse=True)
        limits = {"regular_mod": 8, "exilus_mod": 1, "stance_mod": 1}
        counts: dict[str, int] = {}
        for mod in mods: counts[mod.slot] = counts.get(mod.slot, 0) + 1
        for mod in ranked:
            limit = limits.get(mod.slot, 0)
            if counts.get(mod.slot, 0) >= limit: continue
            trial = self._loadout(mods=[*mods, mod], arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
            if not self._legal(trial): continue
            mods.append(mod)
            selected.add(mod.name)
            counts[mod.slot] = counts.get(mod.slot, 0) + 1
        return mods

    def _profile_priority(self, upgrade: Mod | Arcane, profile: set[str]) -> tuple[float, float, int, str]:
        matched = len(set(upgrade.stats) & profile)
        priority, stat_count, name = self._upgrade_priority(upgrade)
        return matched * 100.0 + priority, priority, stat_count, name

    def _perk_sets(self, base: Loadout, pools: dict[str, tuple], limit: int) -> list[list[Perk]]:
        sets = [list(base.evolutions)]
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in base.evolutions if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers: continue
            expanded = []
            for current in sets:
                for perk in choices: expanded.append([*current, perk])
            sets = expanded[:limit] or sets
        return sets[:limit]

    def _exact_neighbors(self, loadout: Loadout, pools: dict[str, tuple]):
        fixed = self.calculator.loadout
        seen: set[tuple] = set()
        for candidate in self._neighbors(loadout, pools, random.Random(0)):
            key = self._loadout_key(candidate)
            if key not in seen:
                seen.add(key)
                yield candidate
        for index in range(len(fixed.mods), len(loadout.mods)):
            selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
            for mod in pools["mods"]:
                if mod.name in selected: continue
                mods = list(loadout.mods)
                mods[index] = mod
                candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        for index in range(len(fixed.arcanes), len(loadout.arcanes)):
            selected = {arcane.name for i, arcane in enumerate(loadout.arcanes) if i != index}
            for arcane in pools["arcanes"]:
                if arcane.name in selected: continue
                arcanes = list(loadout.arcanes)
                arcanes[index] = arcane
                candidate = self._loadout(mods=loadout.mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate

    def _exact_perturbations(self, loadout: Loadout, pools: dict[str, tuple], *, search_scale: float = 1.0):
        fixed = self.calculator.loadout
        mutable = list(range(len(fixed.mods), len(loadout.mods)))
        ranked_limit = min(len(pools["mods"]), max(12, round(48 * search_scale ** 0.45)))
        ranked_mods = tuple(sorted(pools["mods"], key=self._upgrade_priority, reverse=True)[:ranked_limit])
        seen: set[tuple] = set()
        for left_pos in range(len(mutable)):
            for right_pos in range(left_pos + 1, len(mutable)):
                left = mutable[left_pos]
                right = mutable[right_pos]
                selected = {mod.name for index, mod in enumerate(loadout.mods) if index not in {left, right}}
                choices = [mod for mod in ranked_mods if mod.name not in selected]
                pair_limit = max(4, round(16 * search_scale ** 0.35))
                for first in choices[:pair_limit]:
                    for second in choices[:pair_limit]:
                        if first.name == second.name: continue
                        mods = list(loadout.mods)
                        mods[left], mods[right] = first, second
                        candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                        key = self._loadout_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate
        if loadout.arcanes and len(loadout.mods) > len(fixed.mods):
            arcane_limit = min(len(pools["arcanes"]), max(8, round(48 * search_scale ** 0.4)))
            for arcane in pools["arcanes"][:arcane_limit]:
                for index in mutable:
                    selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
                    mod_limit = min(len(ranked_mods), max(6, round(32 * search_scale ** 0.4)))
                    for mod in ranked_mods[:mod_limit]:
                        if mod.name in selected: continue
                        mods = list(loadout.mods)
                        mods[index] = mod
                        arcanes = list(loadout.arcanes)
                        arcanes[len(fixed.arcanes)] = arcane
                        candidate = self._loadout(mods=mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                        key = self._loadout_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate

    def _candidate_group(self, candidate: _Candidate) -> tuple:
        loadout = candidate.loadout
        arcane = loadout.arcanes[0].name if loadout.arcanes else ""
        elements: set[str] = set()
        orientation: set[str] = set()
        for upgrade in loadout.ranked_upgrades:
            stats = set(upgrade.stats)
            elements.update(stats & {"heat", "cold", "electricity", "toxin", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "void"})
            if stats & {"crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage"}: orientation.add("crit")
            if stats & {"status_chance", "status_damage"}: orientation.add("status")
            if stats & {"multishot"}: orientation.add("multishot")
            if stats & {"fire_rate", "multiplicative_fire_rate", "attack_speed"}: orientation.add("speed")
        perks = tuple(sorted((self.calculator.weapon.perks[perk].tier, perk.name) for perk in loadout.evolutions if perk in self.calculator.weapon.perks))
        progenitor = None if loadout.progenitor is None else loadout.progenitor.element
        riven = next((mod.name for mod in loadout.mods if self._is_riven(mod)), "")
        return arcane, tuple(sorted(elements)), tuple(sorted(orientation)), perks, progenitor, riven

    def _select_diverse(self, candidates: list[_Candidate], limit: int) -> list[_Candidate]:
        ordered = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
        unique: list[_Candidate] = []
        seen_keys: set[tuple] = set()
        for candidate in ordered:
            key = self._loadout_key(candidate.loadout)
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(candidate)
        global_limit = max(1, int(limit * 0.6))
        selected = unique[:global_limit]
        selected_keys = {self._loadout_key(candidate.loadout) for candidate in selected}
        seen_groups = {self._candidate_group(candidate) for candidate in selected}
        for candidate in unique[global_limit:]:
            if len(selected) >= limit: break
            group = self._candidate_group(candidate)
            key = self._loadout_key(candidate.loadout)
            if group not in seen_groups and key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
                seen_groups.add(group)
        for candidate in unique:
            if len(selected) >= limit: break
            key = self._loadout_key(candidate.loadout)
            if key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
        return selected

    def _perturbations(self, loadout: Loadout, pools: dict[str, tuple], rng: random.Random):
        fixed = self.calculator.loadout
        mutable_mods = list(range(len(fixed.mods), len(loadout.mods)))
        if len(mutable_mods) >= 2:
            pairs = [(mutable_mods[i], mutable_mods[j]) for i in range(len(mutable_mods)) for j in range(i + 1, len(mutable_mods))]
            rng.shuffle(pairs)
            for first, second in pairs[:8]:
                selected = {mod.name for index, mod in enumerate(loadout.mods) if index not in {first, second}}
                replacements = [mod for mod in pools["mods"] if mod.name not in selected]
                if len(replacements) < 2: continue
                for _ in range(2):
                    left, right = rng.sample(replacements, 2)
                    mods = list(loadout.mods)
                    mods[first], mods[second] = left, right
                    candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                    if self._legal(candidate): yield candidate
        if loadout.arcanes and len(loadout.mods) > len(fixed.mods):
            arcane_index = len(fixed.arcanes)
            if arcane_index < len(loadout.arcanes):
                mod_indices = list(range(len(fixed.mods), len(loadout.mods)))
                rng.shuffle(mod_indices)
                for mod_index in mod_indices[:4]:
                    for arcane in rng.sample(list(pools["arcanes"]), min(4, len(pools["arcanes"]))):
                        selected = {mod.name for index, mod in enumerate(loadout.mods) if index != mod_index}
                        choices = [mod for mod in pools["mods"] if mod.name not in selected]
                        if not choices: continue
                        mods = list(loadout.mods)
                        mods[mod_index] = rng.choice(choices)
                        arcanes = list(loadout.arcanes)
                        arcanes[arcane_index] = arcane
                        candidate = self._loadout(mods=mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                        if self._legal(candidate): yield candidate

    def _cleanup_removals(self, loadout: Loadout) -> list[tuple[int, Loadout]]:
        fixed = self.calculator.loadout
        removals: list[tuple[int, Loadout]] = []
        for index in range(len(fixed.mods), len(loadout.mods)):
            candidate = self._loadout(mods=[mod for i, mod in enumerate(loadout.mods) if i != index], arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
            if self._legal(candidate): removals.append((index, candidate))
        offset = len(loadout.mods)
        for index in range(len(fixed.arcanes), len(loadout.arcanes)):
            candidate = self._loadout(mods=loadout.mods, arcanes=[arcane for i, arcane in enumerate(loadout.arcanes) if i != index], evolutions=loadout.evolutions, progenitor=loadout.progenitor)
            if self._legal(candidate): removals.append((offset + index, candidate))
        return removals

    def _cleanup_replacements(self, loadout: Loadout, pools: dict[str, tuple], weak_indices: list[int], *, limit: int) -> list[Loadout]:
        fixed = self.calculator.loadout
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in fixed.evolutions if perk in self.calculator.weapon.perks}
        candidates: dict[tuple, Loadout] = {}
        for encoded_index in weak_indices:
            if encoded_index < len(loadout.mods):
                index = encoded_index
                selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
                ranked = sorted((mod for mod in pools["mods"] if mod.name not in selected), key=self._upgrade_priority, reverse=True)[:limit]
                for mod in ranked:
                    mods = list(loadout.mods)
                    mods[index] = mod
                    candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                    if self._legal(candidate): candidates.setdefault(self._loadout_key(candidate), candidate)
            else:
                index = encoded_index - len(loadout.mods)
                if index < len(fixed.arcanes): continue
                selected = {arcane.name for i, arcane in enumerate(loadout.arcanes) if i != index}
                ranked = sorted((arcane for arcane in pools["arcanes"] if arcane.name not in selected), key=self._upgrade_priority, reverse=True)[:limit]
                for arcane in ranked:
                    arcanes = list(loadout.arcanes)
                    arcanes[index] = arcane
                    candidate = self._loadout(mods=loadout.mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                    if self._legal(candidate): candidates.setdefault(self._loadout_key(candidate), candidate)
        tier_indices = {self.calculator.weapon.perks[perk].tier: index for index, perk in enumerate(loadout.evolutions) if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers or tier not in tier_indices: continue
            index = tier_indices[tier]
            for perk in choices:
                if perk == loadout.evolutions[index]: continue
                evolutions = list(loadout.evolutions)
                evolutions[index] = perk
                candidate = self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=evolutions, progenitor=loadout.progenitor)
                candidates.setdefault(self._loadout_key(candidate), candidate)
        if fixed.progenitor is None:
            for progenitor in pools["progenitors"]:
                if progenitor == loadout.progenitor: continue
                candidate = self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=progenitor)
                candidates.setdefault(self._loadout_key(candidate), candidate)
        return sorted(candidates.values(), key=self._estimate_loadout, reverse=True)[:max(limit * max(1, len(weak_indices)), limit)]

    def _random_loadout(self, base: Loadout, pools: dict[str, tuple], rng: random.Random) -> Loadout:
        mods = list(base.mods)
        selected = {mod.name for mod in mods}
        for mod in rng.sample(list(pools["mods"]), min(max(0, 8 - len(mods)), len(pools["mods"]))):
            if mod.name not in selected:
                mods.append(mod)
                selected.add(mod.name)
        arcanes = list(base.arcanes)
        if not arcanes and pools["arcanes"]: arcanes.append(rng.choice(pools["arcanes"]))
        perks = list(base.evolutions)
        occupied = {self.calculator.weapon.perks[perk].tier for perk in perks if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier not in occupied: perks.append(rng.choice(choices))
        progenitor = base.progenitor or (rng.choice(pools["progenitors"]) if pools["progenitors"] else None)
        candidate = self._loadout(mods=mods, arcanes=arcanes, evolutions=perks, progenitor=progenitor)
        return candidate if self._legal(candidate) else base.copy()

    def _shortlist(self, pool: tuple, selected: set[str], limit: int) -> tuple:
        return tuple(upgrade for upgrade in pool if upgrade.name not in selected)[:limit]

    def _legal(self, loadout: Loadout) -> bool:
        if sum(self._is_riven(mod) for mod in loadout.mods) > 1: return False
        upgrades = list(loadout.ranked_upgrades)
        names = {upgrade.name for upgrade in upgrades}
        if len(names) != len(upgrades): return False
        for upgrade in upgrades:
            if any(conflict in names for conflict in upgrade.conflicts): return False
        slot_counts: dict[str, int] = {}
        for mod in loadout.mods: slot_counts[mod.slot] = slot_counts.get(mod.slot, 0) + 1
        if slot_counts.get("regular_mod", 0) > 8 or slot_counts.get("exilus_mod", 0) > 1 or slot_counts.get("stance_mod", 0) > 1: return False
        return True

    def _component_id(self, component: object) -> int:
        identity = id(component)
        cached = self._component_id_cache.get(identity)
        if cached is not None and cached[0] is component: return cached[1]
        assigned = self._next_component_id
        self._next_component_id += 1
        self._component_id_cache[identity] = component, assigned
        return assigned

    def _compiled_upgrade_effects(self, loadout: Loadout) -> tuple[ResolvedEffect, ...]:
        upgrades = loadout.ranked_upgrades
        key = tuple(self._component_id(upgrade) for upgrade in upgrades)
        cached = self._upgrade_effects_cache.get(key)
        if cached is not None: return cached
        groups: list[tuple[ResolvedEffect, ...]] = []
        for upgrade in upgrades:
            if not upgrade.implemented: continue
            component_id = self._component_id(upgrade)
            effects = self._resolved_effect_cache.get(component_id)
            if effects is None:
                effects = upgrade.resolve_manual()
                self._resolved_effect_cache[component_id] = effects
            groups.append(effects)
        compiled = tuple(effect for effects in groups for effect in effects)
        self._upgrade_effects_cache[key] = compiled
        return compiled

    def _loadout_key(self, loadout: Loadout) -> tuple:
        return (tuple(self._component_id(mod) for mod in loadout.mods), tuple(self._component_id(arcane) for arcane in loadout.arcanes), tuple(self._component_id(perk) for perk in loadout.evolutions), None if loadout.progenitor is None else (loadout.progenitor.element, loadout.progenitor.bonus))

