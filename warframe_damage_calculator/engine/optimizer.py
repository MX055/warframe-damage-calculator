from __future__ import annotations

import heapq
import math
import random
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from itertools import combinations, permutations, product

from ..database.arsenal import arsenal
from ..domain.loadouts import Loadout, Progenitor
from ..domain.results import CalculationResult
from ..domain.upgrades import Arcane, Mod, Perk, UpgradeStats
from .calculator import Calculator

Metric = Callable[[CalculationResult], float]

RIVEN_ROLLS = ((2, 0, 0.99, 0.0), (2, 1, 1.2375, -0.495), (3, 0, 0.75, 0.0), (3, 1, 0.9375, -0.75))
RIVEN_NON_NEGATIVE = frozenset({"cold", "electricity", "heat", "punch_through", "toxin"})
RIVEN_RELEVANT = frozenset({"damage_bonus", "cold", "crit_chance", "crit_damage", "corpus_damage", "electricity", "fire_rate", "grineer_damage", "heat", "impact", "infested_damage", "magazine_capacity", "multishot", "punch_through", "puncture", "reload_speed", "slash", "status_chance", "status_duration", "toxin"})


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




@dataclass(slots=True)
class _ProgressSnapshot:
    completed: int = 0
    estimated_total: int = 1
    phase: str = "Seeds"
    phase_started: int = 0
    phase_total: int = 1
    complete: bool = False


class _ProgressReporter:
    __slots__ = ("_enabled", "_started", "_interval", "_state", "_lock", "_render_lock", "_stop", "_thread", "_last_length", "_progress", "_samples", "_display_eta")

    def __init__(self, enabled: bool, *, interval: float = 0.1) -> None:
        self._enabled = enabled
        self._started = time.perf_counter()
        self._interval = interval
        self._state = _ProgressSnapshot()
        self._lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="optimizer-progress", daemon=True) if enabled else None
        self._last_length = 0
        self._progress = 0.0
        self._samples: deque[tuple[float, int]] = deque(maxlen=64)
        self._samples.append((self._started, 0))
        self._display_eta: float | None = None
        if self._thread is not None: self._thread.start()

    def set_estimated_total(self, estimated_total: int) -> None:
        if not self._enabled: return
        with self._lock:
            self._state.estimated_total = max(int(estimated_total), self._state.completed + 1, 1)

    def begin_phase(self, stage: str, planned: int, *, completed: int) -> None:
        if not self._enabled: return
        with self._lock:
            self._state.completed = completed
            self._state.phase = stage
            self._state.phase_started = completed
            self._state.phase_total = max(int(planned), 1)

    def update_plan(self, planned_remaining: int) -> None:
        if not self._enabled: return
        with self._lock:
            phase_done = max(self._state.completed - self._state.phase_started, 0)
            self._state.phase_total = max(phase_done + int(planned_remaining), phase_done + 1, 1)

    def record_evaluation(self, completed: int) -> None:
        if not self._enabled: return
        now = time.perf_counter()
        with self._lock:
            self._state.completed = completed
            self._samples.append((now, completed))

    def abort(self) -> None:
        if not self._enabled: return
        self._stop.set()
        assert self._thread is not None
        self._thread.join()

    def close(self, *, completed: int) -> None:
        if not self._enabled: return
        with self._lock:
            self._state.completed = completed
            self._state.complete = True
            self._progress = 1.0
        self._stop.set()
        assert self._thread is not None
        self._thread.join()
        self._render(final=True)

    def _run(self) -> None:
        self._render()
        while not self._stop.wait(self._interval): self._render()

    def _eta(self) -> tuple[float | None, str]:
        with self._lock:
            samples = tuple(self._samples)
            completed = self._state.completed
            remaining = max(self._state.estimated_total - completed, 0)
        if completed < 16 or len(samples) < 2: return None, "estimating"
        first_time, first_count = samples[0]
        last_time, last_count = samples[-1]
        recent_completed = last_count - first_count
        recent_elapsed = last_time - first_time
        total_elapsed = last_time - self._started
        if recent_completed <= 0 or recent_elapsed <= 0 or completed <= 0: return None, "estimating"
        recent_seconds = recent_elapsed / recent_completed
        overall_seconds = total_elapsed / completed
        seconds_per_evaluation = 0.65 * recent_seconds + 0.35 * overall_seconds
        eta = max(remaining * seconds_per_evaluation, 0.1)
        if self._display_eta is None: self._display_eta = eta
        else:
            alpha = 0.12 if eta < self._display_eta else 0.25
            self._display_eta = alpha * eta + (1 - alpha) * self._display_eta
        return self._display_eta, "ready"


    def _phase_progress(self) -> float:
        weights = {"Seeds": 0.12, "Local search": 0.53, "Perturbations": 0.20, "Cleanup": 0.15, "Exhaustive": 1.0}
        order = ("Seeds", "Local search", "Perturbations", "Cleanup") if self._state.phase != "Exhaustive" else ("Exhaustive",)
        with self._lock:
            phase = self._state.phase
            phase_done = max(self._state.completed - self._state.phase_started, 0)
            phase_total = max(self._state.phase_total, 1)
        try:
            index = order.index(phase)
        except ValueError:
            return self._progress
        base = sum(weights[name] for name in order[:index])
        fraction = min(phase_done / phase_total, 0.95)
        return min(base + weights[phase] * fraction, 0.985)

    def _render(self, *, final: bool = False) -> None:
        with self._render_lock:
            with self._lock:
                complete = self._state.complete
                completed = self._state.completed
                estimated_total = self._state.estimated_total
            elapsed = time.perf_counter() - self._started
            eta, eta_state = self._eta()
            if complete:
                progress = 1.0
            else:
                estimated_progress = self._phase_progress()
                with self._lock:
                    self._progress = min(max(self._progress, estimated_progress), 0.985)
                    progress = self._progress
            width = 30
            filled = width if complete else min(width - 1, int(progress * width))
            bar = "█" * filled + "·" * (width - filled)
            label = "Complete" if complete else "Optimizing"
            message = f"{label} [{bar}] {progress:6.2%} · {elapsed:,.1f}s elapsed"
            if not complete:
                if eta_state == "estimating": message += " · estimating ETA"
                elif eta is not None: message += f" · {eta:,.1f}s ETA"
            padding = " " * max(0, self._last_length - len(message))
            print(f"\r{message}{padding}", end="\n" if final else "", file=sys.stdout, flush=True)
            self._last_length = len(message)

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
    result: CalculationResult


class Optimizer:
    __slots__ = ("calculator", "_priority_cache")

    def __init__(self, calculator: Calculator) -> None:
        if not isinstance(calculator, Calculator): raise TypeError("calculator must be a Calculator")
        self.calculator = calculator
        self._priority_cache: dict[tuple, tuple[float, int, str]] = {}

    def resolve(self, metric: Metric = default_metric, *, attacks: Mapping[str, float] | None = None, bodyparts: Mapping[str, float] | None = None, evaluations: int = 10_000, progress: bool = True, riven: bool = True) -> Optimization:
        if not callable(metric): raise TypeError("metric must be callable")
        if evaluations < 1: raise ValueError("evaluations must be at least 1")
        if not isinstance(progress, bool): raise TypeError("progress must be a bool")
        if not isinstance(riven, bool): raise TypeError("riven must be a bool")
        started = time.perf_counter()
        resolution_budget = evaluations
        search_scale = max(0.25, math.sqrt(evaluations / 5_000))
        mode_scale = 2.0
        reporter = _ProgressReporter(progress)
        attack_weights = self._normalize(attacks, self.calculator.weapon.default_attack, "attack")
        default_bodypart = "body" if self.calculator.target is None else next(iter(self.calculator.target.bodyparts))
        bodypart_weights = self._normalize(bodyparts, default_bodypart, "body part")
        pools = self._candidate_pools(riven=riven, search_scale=search_scale)
        base = self._complete_fixed_loadout(self.calculator.loadout)
        scenarios = []
        for attack, attack_weight in attack_weights.items():
            for bodypart, bodypart_weight in bodypart_weights.items():
                evaluator = Calculator(self.calculator.weapon, self.calculator.target, base)
                selected_bodypart, target = evaluator._select_bodypart(bodypart)
                scenarios.append((evaluator, attack, selected_bodypart, target, attack_weight * bodypart_weight))
        cache: dict[tuple, _Candidate] = {}
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
            for evaluator, attack, bodypart, target, weight in scenarios:
                evaluator.loadout = loadout
                result = evaluator._calculate(attack, bodypart, target, {}, copy_inputs=False)
                value = float(metric(result))
                if not math.isfinite(value): raise ValueError("metric must return a finite number")
                score += weight * value
                representative = representative or result
                resolutions += 1
            assert representative is not None
            candidate = _Candidate(loadout, score, representative)
            cache[key] = candidate
            evaluations_used += 1
            reporter.record_evaluation(evaluations_used)
            return candidate, True

        best = _Candidate(base, float("-inf"), self.calculator.resolve())
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
        reporter.close(completed=evaluations_used)
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
        return Optimization(best.loadout.copy(), best.result, best.score, evaluations_used, resolutions, attempts, cache_hits, 0, elapsed, summary)

    def _loadout(self, *, mods=(), arcanes=(), evolutions=(), progenitor=None) -> Loadout:
        return Loadout._from_parts(mods=mods, arcanes=arcanes, evolutions=evolutions, progenitor=progenitor)

    def _normalize(self, values: Mapping[str, float] | None, default: str, label: str) -> dict[str, float]:
        supplied = {default: 1.0} if values is None else {str(name): float(weight) for name, weight in values.items()}
        if not supplied: raise ValueError(f"{label} weights cannot be empty")
        if any(weight < 0 for weight in supplied.values()): raise ValueError(f"{label} weights cannot be negative")
        supplied = {name: weight for name, weight in supplied.items() if weight > 0}
        total = sum(supplied.values())
        if total == 0: raise ValueError(f"{label} weights must contain a positive value")
        return {name: weight / total for name, weight in supplied.items()}

    def _candidate_pools(self, *, riven: bool = True, search_scale: float = 1.0) -> dict[str, tuple]:
        weapon = self.calculator.weapon
        compatible_mods = arsenal.mod.filter(weapon=weapon, implemented=True)
        mod_limit = min(192, max(36, round(108 * search_scale ** 0.4)))
        regular_mods = self._prepare_pool(compatible_mods, mod_limit)
        locked_riven = any(self._is_riven(mod) for mod in self.calculator.loadout.mods)
        riven_limit = min(192, max(16, round(64 * search_scale ** 0.5)))
        rivens = () if locked_riven or not riven else self._riven_candidates(limit=riven_limit)
        mods = (*regular_mods, *rivens)
        compatible_arcanes = arsenal.arcane.filter(weapon=weapon, implemented=True)
        arcane_limit = min(96, max(18, round(54 * search_scale ** 0.4)))
        arcanes = self._prepare_pool(compatible_arcanes, arcane_limit)
        perks = {tier: implemented for tier, choices in weapon.perk_choices.items() if (implemented := tuple(perk for perk in choices.values() if perk.implemented))}
        progenitors = tuple(Progenitor(element, 0.6) for element in ("impact", "heat", "cold", "electricity", "toxin", "magnetic", "radiation")) if "progenitor" in weapon.traits else ()
        return {"mods": mods, "arcanes": arcanes, "perks": perks, "progenitors": progenitors, "rivens": rivens}

    def _riven_candidates(self, *, limit: int = 32) -> tuple[Mod, ...]:
        category = self._riven_category()
        if category is None or self.calculator.weapon.disposition <= 0: return ()
        base_stats = arsenal.database.get("riven_stats", {}).get(category, {})
        if not base_stats: return ()
        positive_stats = [stat for stat in base_stats if stat in RIVEN_RELEVANT]
        positive_stats.sort(key=lambda stat: self._riven_stat_priority(stat, float(base_stats[stat])), reverse=True)
        positive_stats = positive_stats[:14 if limit > 32 else 10]
        negative_stats = [stat for stat in base_stats if stat not in RIVEN_NON_NEGATIVE]
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

    def _complete_fixed_loadout(self, source: Loadout) -> Loadout:
        perks = list(source.evolutions)
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

    def _loadout_key(self, loadout: Loadout) -> tuple:
        def upgrade_key(upgrade: Mod | Arcane) -> tuple:
            stats = tuple((stat, tuple((effect.value, effect.mode, effect.family, effect.maximum) for effect in effects)) for stat, effects in sorted(upgrade.stats.items()))
            return upgrade.name, upgrade.slot, tuple(sorted(upgrade.runtime.as_dict().items())), stats
        return (tuple(upgrade_key(mod) for mod in loadout.mods), tuple(upgrade_key(arcane) for arcane in loadout.arcanes), tuple(perk.name for perk in loadout.evolutions), None if loadout.progenitor is None else (loadout.progenitor.element, loadout.progenitor.bonus))
