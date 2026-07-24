from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from ..fields.evolution import ConversionBonus, EvolutionPerk, ResolvedEvolutionStat
from ..models.data import Data
from ..protocols import WeaponCalculatorOwner
from ..utils.constants import EFFECT_MODES
from ..utils.types import EffectMode, Number


type EffectBucket = Literal["static", "conditional", "stacking"]
type EffectValue = Number | bool | Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _Effect:
    stat: str
    value: EffectValue
    bucket: EffectBucket
    mode: EffectMode = "additive"
    condition: str | None = None
    stacks_on: str | None = None
    max_stacks: int | None = None
    conversion_max: Number | None = None


@dataclass(frozen=True, slots=True)
class _ResolutionContext:
    runtime: Data
    use_defaults: bool


class EvolutionCalculator:
    CONVERSION_STATS = frozenset({"crit_from_status", "status_from_crit"})

    def __init__(self, weapon: WeaponCalculatorOwner, runtime: Mapping[str, Any] | None = None) -> None:
        self.weapon = weapon
        self.runtime = Data(runtime or {})
        self.total = ResolvedEvolutionStat()
        self.resolve()

    @staticmethod
    def _raw_effects(raw: Any) -> list[Data]:
        values = raw if isinstance(raw, list) else [raw]
        effects: list[Data] = []
        for value in values:
            if isinstance(value, Mapping):
                effects.append(value if isinstance(value, Data) else Data(value))
            else:
                effects.append(Data({"value": value}))
        return effects

    def _normalize_effect(self, stat: str, effect: Data) -> _Effect:
        raw_mode = effect.get("mode", "additive")
        if raw_mode not in EFFECT_MODES:
            raise ValueError(f"unsupported effect mode {raw_mode!r}")
        mode = cast(EffectMode, raw_mode)

        condition = effect.get("when")
        stacks = effect.get("stacks")
        value = effect.value
        conversion_max = effect.get("max")

        if stacks is not None:
            return _Effect(stat, value, "stacking", mode=mode, stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), conversion_max=conversion_max)
        if condition is None:
            return _Effect(stat, value, "static", mode=mode, conversion_max=conversion_max)
        return _Effect(stat, value, "conditional", mode=mode, condition=condition, conversion_max=conversion_max)

    def _selected_perks(self) -> list[EvolutionPerk]:
        evolutions = self.weapon.data.evolutions
        perks: list[EvolutionPerk] = []
        for tier, perk in self.weapon.data.selected_evolutions.items():
            tier_data = evolutions.get(str(tier))
            if tier_data is None:
                continue
            perk_data = tier_data.get(str(perk))
            if perk_data is None:
                continue
            perks.append(perk_data if isinstance(perk_data, EvolutionPerk) else EvolutionPerk(perk_data))
        return perks

    def _normalize_effects(self) -> tuple[_Effect, ...]:
        effects: list[_Effect] = []
        for perk in self._selected_perks():
            for stat, raw in perk.stats.items():
                for effect in self._raw_effects(raw):
                    effects.append(self._normalize_effect(stat, effect))
        return tuple(effects)

    def _condition(self, condition: str) -> bool:
        return bool(self.runtime.get(condition, True))

    def _stack_count(self, effect: _Effect, context: _ResolutionContext) -> int:
        stacks_value = context.runtime.get("stacks")
        if stacks_value is None:
            fallback = (effect.max_stacks or 0) if context.use_defaults else 0
        else:
            fallback = stacks_value
        stacks = context.runtime.get(effect.stacks_on, fallback)
        return min(stacks, effect.max_stacks) if effect.max_stacks is not None else stacks

    def _is_effect_applicable(self, effect: _Effect, context: _ResolutionContext) -> bool:
        if effect.condition is not None and not self._condition(effect.condition):
            return False
        return True

    def _resolve_effect(self, effect: _Effect, context: _ResolutionContext) -> _Effect | None:
        stacks = 1
        if effect.stacks_on is not None:
            stacks = self._stack_count(effect, context)
            if not stacks:
                return None
        value = effect.value
        if effect.stacks_on is not None and not isinstance(value, bool):
            value = value * stacks
        return replace(effect, value=value)

    def _resolve_effects(self, effects: Iterable[_Effect], context: _ResolutionContext) -> tuple[_Effect, ...]:
        resolved: list[_Effect] = []
        for effect in effects:
            if not self._is_effect_applicable(effect, context):
                continue
            resolved_effect = self._resolve_effect(effect, context)
            if resolved_effect is not None:
                resolved.append(resolved_effect)
        return tuple(resolved)

    def _merge_conversion(self, stats: Data, stat: str, value: Number, conversion_max: Number | None) -> None:
        current = stats.get(stat)
        if not isinstance(current, ConversionBonus):
            current = ConversionBonus()
        current.value = float(current.value) + float(value)
        if conversion_max is not None:
            current.max = max(float(current.max), float(conversion_max))
        stats[stat] = current

    def _merge_stat(self, stats: Data, stat: str, value: EffectValue, conversion_max: Number | None = None) -> None:
        if stat in self.CONVERSION_STATS:
            self._merge_conversion(stats, stat, float(value), conversion_max)
            return
        current = stats.get(stat)
        if current is None:
            stats[stat] = value
        elif isinstance(value, bool):
            stats[stat] = current or value
        else:
            stats[stat] = current + value

    def _aggregate_effects(self, effects: Iterable[_Effect]) -> None:
        self.total = ResolvedEvolutionStat()
        for effect in effects:
            self._merge_stat(getattr(self.total, effect.mode), effect.stat, effect.value, effect.conversion_max)

    def resolve(self) -> ResolvedEvolutionStat:
        use_defaults = not self.runtime
        context = _ResolutionContext(runtime=self.runtime, use_defaults=use_defaults)
        effects = self._normalize_effects()
        applicable = self._resolve_effects(effects, context)
        self._aggregate_effects(applicable)
        return self.total
