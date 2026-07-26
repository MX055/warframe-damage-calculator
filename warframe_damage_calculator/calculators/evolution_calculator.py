"""Evolution effect resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..fields.evolution import EvolutionPerk, ResolvedEvolutionModeStats, ResolvedEvolutionStat
from ..core.data import Data
from ..protocols import WeaponCalculatorOwner
from ..utils.types import EffectMode
from .effect_resolution import ResolutionContext, ResolvableEffect, raw_effects, resolve_and_aggregate, resolve_stack_scaled_effect
from .effect_schema import (
    BEHAVIOR_FIRST_SHOT,
    BEHAVIOR_LAST_SHOT,
    BEHAVIOR_MULTISHOT_CONSUMES_AMMO,
    BEHAVIOR_ON_NON_CRIT,
    COMMON_FAMILY,
    MULTISHOT_AMMO_FAMILY,
    NON_CRIT_FAMILY,
    behavior_data_of,
    behavior_of,
    effect_family,
    is_automatic,
    normalize_mode,
)
from .magazine_position import MAGAZINE_POSITION_WHEN, serialize_position_effect
from .stat_aggregation import CONVERSION_STATS, merge_evolution_stat


class EvolutionCalculator:
    CONVERSION_STATS = CONVERSION_STATS

    def __init__(self, weapon: WeaponCalculatorOwner, runtime: Mapping[str, Any], *, form: str | None = None) -> None:
        self.weapon = weapon
        self.runtime = Data(runtime)
        self.form = form
        self.total = ResolvedEvolutionStat()
        self.resolve()

    @staticmethod
    def _exclude_flags(effect: Data) -> tuple[str, ...]:
        exclude = effect.get("exclude")
        if exclude is None: return ()
        return tuple(exclude) if isinstance(exclude, list) else (str(exclude),)

    def _normalize_effect(self, stat: str, effect: Data) -> ResolvableEffect:
        mode = cast(EffectMode, normalize_mode(effect.get("mode")))
        family = effect_family(effect)
        behavior = behavior_of(effect)
        condition = effect.get("when")
        scope = effect.get("scope")
        stacks = effect.get("stacks")
        value = effect.value
        conversion_max = effect.get("max")
        exclude = self._exclude_flags(effect)

        if behavior is not None:
            behavior_data_of(effect, behavior=behavior)

        if behavior == BEHAVIOR_FIRST_SHOT:
            if family == COMMON_FAMILY: family = "chamber"
            return ResolvableEffect(stat=stat, value=value, mode="proportional", bucket="magazine_position", condition="first_shot", scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        if behavior == BEHAVIOR_LAST_SHOT:
            if family == COMMON_FAMILY: family = "charge"
            return ResolvableEffect(stat=stat, value=value, mode="proportional", bucket="magazine_position", condition="last_shot", scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        if behavior == BEHAVIOR_ON_NON_CRIT:
            if stat != "damage_bonus": raise ValueError("ON_NON_CRIT requires damage_bonus")
            if not is_automatic(effect, behavior=behavior): raise ValueError("ON_NON_CRIT requires automatic: true")
            if family == COMMON_FAMILY: family = NON_CRIT_FAMILY
            return ResolvableEffect(stat="damage_bonus", value=value, mode="proportional", bucket="static", scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        if behavior == BEHAVIOR_MULTISHOT_CONSUMES_AMMO:
            if stat != "damage_bonus": raise ValueError("MULTISHOT_CONSUMES_AMMO requires damage_bonus")
            if not is_automatic(effect, behavior=behavior): raise ValueError("MULTISHOT_CONSUMES_AMMO requires automatic: true")
            if family == COMMON_FAMILY: family = MULTISHOT_AMMO_FAMILY
            bucket = "static" if condition is None else "conditional"
            return ResolvableEffect(stat="damage_bonus", value=value, mode="proportional", bucket=bucket, condition=condition, scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        if condition in MAGAZINE_POSITION_WHEN:
            return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="magazine_position", condition=condition, scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        if stacks is not None: return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="stacking", scope=scope, stacks_on=stacks["when"], max_stacks=stacks.get("max"), exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        if condition is None: return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="static", scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)
        return ResolvableEffect(stat=stat, value=value, mode=mode, bucket="conditional", condition=condition, scope=scope, exclude=exclude, family=family, conversion_max=conversion_max, behavior=behavior)

    def _selected_perks(self) -> list[EvolutionPerk]:
        evolutions = self.weapon.data.evolutions
        perks: list[EvolutionPerk] = []
        tier_one = evolutions.get("1")
        if tier_one is not None:
            perk_data = tier_one.get("1")
            if perk_data is not None: perks.append(perk_data if isinstance(perk_data, EvolutionPerk) else EvolutionPerk(perk_data))
        for tier, perk in self.weapon.data.selected_evolutions.items():
            if str(tier) == "1": continue
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
                    normalized = self._normalize_effect(stat, effect)
                    effects.append(normalized)
                    if behavior_of(effect) == BEHAVIOR_ON_NON_CRIT:
                        chance = behavior_data_of(effect, behavior=BEHAVIOR_ON_NON_CRIT).get("chance")
                        if chance is not None:
                            effects.append(ResolvableEffect(stat="non_crit_bonus_chance", value=float(chance), mode="proportional", bucket=normalized.bucket, scope=normalized.scope, scales_with_rank=False, behavior=BEHAVIOR_ON_NON_CRIT))
        return tuple(effects)

    def _is_effect_applicable(self, effect: ResolvableEffect, context: ResolutionContext) -> bool:
        if effect.scope is not None and context.form is not None and effect.scope != context.form:
            return False
        if effect.bucket == "magazine_position" or effect.condition is None: return True
        return bool(context.runtime[effect.condition])

    def _resolve_effect(self, effect: ResolvableEffect, context: ResolutionContext) -> ResolvableEffect | None:
        return resolve_stack_scaled_effect(effect, context)

    def _record_family(self, effect: ResolvableEffect) -> None:
        current = self.total.multiplicative_families.get(effect.family)
        if not isinstance(current, ResolvedEvolutionModeStats):
            current = ResolvedEvolutionModeStats(current) if isinstance(current, Mapping) else ResolvedEvolutionModeStats()
            self.total.multiplicative_families[effect.family] = current
        merge_evolution_stat(current, effect.stat, effect.value, conversion_max=effect.conversion_max)

    def _aggregate_effects(self, effects: Sequence[ResolvableEffect]) -> None:
        self.total = ResolvedEvolutionStat()
        for effect in effects:
            if effect.bucket == "magazine_position":
                entry = serialize_position_effect(stat=effect.stat, value=effect.value, when=effect.condition or "", exclude=effect.exclude, family=effect.family, mode=effect.mode)
                self.total.magazine_position = [*(self.total.magazine_position or []), entry]
                continue
            if effect.mode == "proportional" and effect.family != COMMON_FAMILY:
                self._record_family(effect)
                continue
            merge_evolution_stat(getattr(self.total, effect.mode), effect.stat, effect.value, conversion_max=effect.conversion_max)

    def resolve(self) -> ResolvedEvolutionStat:
        context = ResolutionContext(runtime=self.runtime, form=self.form)
        resolve_and_aggregate(self._normalize_effects(), context, is_applicable=self._is_effect_applicable, resolve_one=self._resolve_effect, aggregate=self._aggregate_effects)
        return self.total
