"""Shared effect-resolution engine for upgrades and evolutions.

Lifecycle owned here:
normalize source data → evaluate applicability → resolve stacks/rank → aggregate.

Source-specific calculators provide normalization, applicability, and aggregation
policy; they do not duplicate the resolve loop.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from ..core.data import Data
from ..utils.types import EffectMode, Number

T = TypeVar("T")
C = TypeVar("C")

type EffectValue = Number | bool | Mapping[str, object] | Any


@dataclass(frozen=True, slots=True)
class ResolvableEffect:
    """Normalized effect shared by upgrades and evolutions."""

    stat: str
    value: EffectValue
    mode: EffectMode = "additive"
    bucket: str = "static"
    condition: str | None = None
    stacks_on: str | None = None
    max_stacks: int | None = None
    required_rank: int | None = None
    equipped: tuple[str, ...] | None = None
    scales_with_rank: bool = False
    co_max_stacks: int | str | None = None
    conversion_max: Number | None = None


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    """Values consulted during applicability and stack/rank resolution."""

    rank: int = 0
    rank_multiplier: float = 1.0
    max_stacks: int | None = None
    use_defaults: bool = False
    stacks_lookup: Mapping[str, Any] | None = None
    default_stacks: Any = None
    equipped: Collection[str] = ()
    weapon: Data | None = None
    upgrade: Data | None = None
    build: Data | None = None
    runtime: Data | None = None


def raw_effects(raw: Any) -> list[Data]:
    values = raw if isinstance(raw, list) else [raw]
    effects: list[Data] = []
    for value in values:
        if isinstance(value, Mapping): effects.append(value if isinstance(value, Data) else Data(value))
        else: effects.append(Data({"value": value}))
    return effects


def stack_count(*, stacks_on: str | None, max_stacks: int | None, lookup: Mapping[str, Any], default_stacks: Any, use_defaults: bool) -> int:
    """Resolve a stack count with optional max and default-when-unset behaviour."""
    if stacks_on is None: return 1
    stacks_value = lookup.get(stacks_on)
    if stacks_value is None: stacks_value = (max_stacks or 0) if use_defaults else (default_stacks if default_stacks is not None else 0)
    return min(stacks_value, max_stacks) if max_stacks is not None else stacks_value


def resolve_effect_list(effects: Iterable[T], *, is_applicable: Callable[[T], bool], resolve_one: Callable[[T], T | None]) -> tuple[T, ...]:
    resolved: list[T] = []
    for effect in effects:
        if not is_applicable(effect): continue
        resolved_effect = resolve_one(effect)
        if resolved_effect is not None: resolved.append(resolved_effect)
    return tuple(resolved)


def resolve_and_aggregate(effects: Sequence[T], context: C, *, is_applicable: Callable[[T, C], bool], resolve_one: Callable[[T, C], T | None], aggregate: Callable[[Sequence[T]], None]) -> None:
    """Run the shared resolve pipeline and hand results to a source-specific aggregator."""
    resolved = resolve_effect_list(effects, is_applicable=lambda effect: is_applicable(effect, context), resolve_one=lambda effect: resolve_one(effect, context))
    aggregate(resolved)


def resolve_stack_scaled_effect(effect: ResolvableEffect, context: ResolutionContext, *, scale: Callable[[EffectValue, float], EffectValue] | None = None) -> ResolvableEffect | None:
    """Apply optional rank scaling and stack multiplication to a normalized effect."""
    if effect.stat == "status_effect_stacks":
        payload = dict(effect.value)
        inner = payload["value"]
        if effect.scales_with_rank and scale is not None: inner = scale(inner, context.rank_multiplier)
        return replace(effect, value={**payload, "value": inner})

    stacks = 1
    if effect.stacks_on is not None:
        effect_max = effect.max_stacks if effect.max_stacks is not None else context.max_stacks
        lookup = context.stacks_lookup or {}
        stacks = stack_count(stacks_on=effect.stacks_on, max_stacks=effect_max, lookup=lookup, default_stacks=context.default_stacks, use_defaults=context.use_defaults and context.default_stacks is None)
        if not stacks: return None

    value = effect.value
    if effect.scales_with_rank and scale is not None: value = scale(value, context.rank_multiplier)
    if effect.stat == "condition_overload": value = {"value": value, "max_stacks": effect.co_max_stacks}
    elif effect.stacks_on is not None and not isinstance(value, bool): value = value * stacks
    return replace(effect, value=value)
