"""Evolution effect resolution: source-specific normalization and aggregation.

Uses the shared ResolvableEffect lifecycle in effect_resolution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..fields.evolution import EvolutionPerk, ResolvedEvolutionStat
from ..core.data import Data
from ..protocols import WeaponCalculatorOwner
from ..utils.constants import EFFECT_MODES
from ..utils.types import EffectMode
from .effect_resolution import ResolutionContext, ResolvableEffect, raw_effects, resolve_and_aggregate, resolve_stack_scaled_effect
from .stat_aggregation import CONVERSION_STATS, merge_evolution_stat


class EvolutionCalculator:
    CONVERSION_STATS = CONVERSION_STATS

    def __init__(self, weapon: WeaponCalculatorOwner, runtime: Mapping[str, Any] | None = None) -> None:
        self.weapon = weapon
        self.runtime = Data(runtime or {})
        self.total = ResolvedEvolutionStat()
        self.resolve()

    def _normalize_effect(self, stat: str, effect: Data) -> ResolvableEffect:
        raw_mode = effect.get("mode", "additive")
        if raw_mode not in EFFECT_MODES: raise ValueError(f"unsupported effect mode {raw_mode!r}")
        mode = cast(EffectMode, raw_mode)

        condition = effect.get("when")
        stacks = effect.get("stacks")
        value = effect.value
        conversion_max = effect.get("max")

        if stacks is not None: return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="stacking", stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), conversion_max=conversion_max)
        if condition is None: return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="static", conversion_max=conversion_max)
        return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="conditional", condition=condition, conversion_max=conversion_max)

    def _selected_perks(self) -> list[EvolutionPerk]:
        evolutions = self.weapon.data.evolutions
        perks: list[EvolutionPerk] = []
        for tier, perk in self.weapon.data.selected_evolutions.items():
            tier_data = evolutions.get(str(tier))
            if tier_data is None: continue
            perk_data = tier_data.get(str(perk))
            if perk_data is None: continue
            perks.append(perk_data if isinstance(perk_data, EvolutionPerk) else EvolutionPerk(perk_data))
        return perks

    def _normalize_effects(self) -> tuple[ResolvableEffect, ...]:
        effects: list[ResolvableEffect] = []
        for perk in self._selected_perks():
            for stat, raw in perk.stats.items():
                for effect in raw_effects(raw):
                    effects.append(self._normalize_effect(stat, effect))
        return tuple(effects)

    def _is_effect_applicable(self, effect: ResolvableEffect, context: ResolutionContext) -> bool:
        if effect.condition is None: return True
        runtime = context.runtime or Data()
        return bool(runtime.get(effect.condition, True))

    def _resolve_effect(self, effect: ResolvableEffect, context: ResolutionContext) -> ResolvableEffect | None:
        return resolve_stack_scaled_effect(effect, context)

    def _aggregate_effects(self, effects: Sequence[ResolvableEffect]) -> None:
        self.total = ResolvedEvolutionStat()
        for effect in effects:
            merge_evolution_stat(getattr(self.total, effect.mode), effect.stat, effect.value, conversion_max=effect.conversion_max)

    def resolve(self) -> ResolvedEvolutionStat:
        use_defaults = not self.runtime
        context = ResolutionContext(use_defaults=use_defaults, stacks_lookup=self.runtime, default_stacks=self.runtime.get("stacks"), runtime=self.runtime)
        resolve_and_aggregate(self._normalize_effects(), context, is_applicable=self._is_effect_applicable, resolve_one=self._resolve_effect, aggregate=self._aggregate_effects)
        return self.total
