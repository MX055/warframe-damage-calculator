"""Evolution effect resolution: source-specific normalization and aggregation.

Uses the shared ResolvableEffect lifecycle in effect_resolution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..fields.evolution import EvolutionPerk, ResolvedEvolutionModeStats, ResolvedEvolutionStat
from ..core.data import Data
from ..protocols import WeaponCalculatorOwner
from ..utils.constants import EFFECT_MODES
from ..utils.types import EffectMode
from .effect_resolution import ResolutionContext, ResolvableEffect, raw_effects, resolve_and_aggregate, resolve_stack_scaled_effect
from .magazine_position import MAGAZINE_POSITION_WHEN, serialize_position_effect
from .stat_aggregation import CONVERSION_STATS, merge_evolution_stat


class EvolutionCalculator:
    CONVERSION_STATS = CONVERSION_STATS
    # Selection / session keys that must not disable default stack assumptions.
    _SELECTION_KEYS = frozenset({"evolutions", "attack", "combo", "stance_combo"})

    def __init__(self, weapon: WeaponCalculatorOwner, runtime: Mapping[str, Any] | None = None, *, form: str | None = None) -> None:
        self.weapon = weapon
        self.runtime = Data(runtime if runtime is not None else getattr(weapon.data, "runtime", {}) or {})
        self.form = form
        self.total = ResolvedEvolutionStat()
        self.resolve()

    @staticmethod
    def _exclude_flags(effect: Data) -> tuple[str, ...]:
        exclude = effect.get("exclude")
        if exclude is None: return ()
        return tuple(exclude) if isinstance(exclude, list) else (str(exclude),)

    @staticmethod
    def _effect_tier(effect: Data) -> int:
        return max(int(effect.get("tier") or 1), 1)

    def _normalize_effect(self, stat: str, effect: Data) -> ResolvableEffect:
        raw_mode = effect.get("mode", "additive")
        if raw_mode not in EFFECT_MODES: raise ValueError(f"unsupported effect mode {raw_mode!r}")
        mode = cast(EffectMode, raw_mode)

        condition = effect.get("when")
        scope = effect.get("scope")
        stacks = effect.get("stacks")
        value = effect.value
        conversion_max = effect.get("max")
        exclude = self._exclude_flags(effect)
        tier = self._effect_tier(effect)

        if condition in MAGAZINE_POSITION_WHEN:
            return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="magazine_position", condition=condition, scope=scope, exclude=exclude, tier=tier, conversion_max=conversion_max)
        if stacks is not None: return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="stacking", scope=scope, stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), exclude=exclude, tier=tier, conversion_max=conversion_max)
        if condition is None: return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="static", scope=scope, exclude=exclude, tier=tier, conversion_max=conversion_max)
        return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="conditional", condition=condition, scope=scope, exclude=exclude, tier=tier, conversion_max=conversion_max)

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
        if effect.scope is not None and context.form is not None and effect.scope != context.form:
            return False
        if effect.bucket == "magazine_position" or effect.condition is None: return True
        runtime = context.runtime or Data()
        return bool(runtime.get(effect.condition, True))

    def _resolve_effect(self, effect: ResolvableEffect, context: ResolutionContext) -> ResolvableEffect | None:
        return resolve_stack_scaled_effect(effect, context)

    def _aggregate_effects(self, effects: Sequence[ResolvableEffect]) -> None:
        self.total = ResolvedEvolutionStat()
        for effect in effects:
            if effect.bucket == "magazine_position":
                entry = serialize_position_effect(stat=effect.stat, value=effect.value, mode=effect.mode, when=effect.condition or "", exclude=effect.exclude, tier=effect.tier)
                self.total.magazine_position = [*(self.total.magazine_position or []), entry]
                continue
            if effect.mode == "multiplicative" and effect.tier > 1:
                key = str(effect.tier)
                current = self.total.multiplicative_tiers.get(key)
                if not isinstance(current, ResolvedEvolutionModeStats):
                    current = ResolvedEvolutionModeStats(current) if isinstance(current, Mapping) else ResolvedEvolutionModeStats()
                    self.total.multiplicative_tiers[key] = current
                merge_evolution_stat(current, effect.stat, effect.value, conversion_max=effect.conversion_max)
                continue
            merge_evolution_stat(getattr(self.total, effect.mode), effect.stat, effect.value, conversion_max=effect.conversion_max)

    def resolve(self) -> ResolvedEvolutionStat:
        # Empty runtime, or runtime that only selects attack/evolutions/combo, still
        # assumes max stacks for stacking Incarnon perks (e.g. activation stacks).
        use_defaults = not any(key not in self._SELECTION_KEYS for key in self.runtime)
        context = ResolutionContext(use_defaults=use_defaults, stacks_lookup=self.runtime, default_stacks=self.runtime.get("stacks"), runtime=self.runtime, form=self.form)
        resolve_and_aggregate(self._normalize_effects(), context, is_applicable=self._is_effect_applicable, resolve_one=self._resolve_effect, aggregate=self._aggregate_effects)
        return self.total
