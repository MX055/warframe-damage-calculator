from __future__ import annotations

import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


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
            if progress.complete:
                if self._last_length: print(f"\r{' ' * self._last_length}\r", end="", file=sys.stdout, flush=True)
                self._last_length = 0
                return
            width = 30
            filled = min(width - 1, int(progress.fraction * width))
            bar = "â–ˆ" * filled + "Â·" * (width - filled)
            message = f"Optimizing {bar} {progress.fraction:6.2%} Â· {progress.elapsed:,.1f}s elapsed"
            message += " Â· estimating ETA" if progress.eta is None else f" Â· {progress.eta:,.1f}s ETA"
            padding = " " * max(0, self._last_length - len(message))
            print(f"\r{message}{padding}", end="", file=sys.stdout, flush=True)
            self._last_length = len(message)


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
        weights = {"Seeds": 0.10, "Local search": 0.35, "Perturbations": 0.25, "Rebuilds": 0.20, "Cleanup": 0.10}
        order = ("Seeds", "Local search", "Perturbations", "Rebuilds", "Cleanup")
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

