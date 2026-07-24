"""Upgrade effect resolution: source-specific normalization and aggregation.

Uses the shared ResolvableEffect lifecycle in effect_resolution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..fields.upgrade import ResolvedStat
from ..loader.matching import MELEE_TYPES, PRIMARY_TYPES, SECONDARY_TYPES
from ..core.data import Data
from ..core.dist import Dist
from ..protocols import UpgradeOwner
from ..utils.constants import EFFECT_MODES
from ..utils.types import EffectMode, Number
from .effect_resolution import ResolutionContext, ResolvableEffect, raw_effects, resolve_and_aggregate, resolve_stack_scaled_effect
from .stat_aggregation import merge_resolved_stat, merge_upgrade_stat


type EffectValue = Number | bool | Mapping[str, object] | Dist


class UpgradeCalculator:
    static: ResolvedStat
    conditional: ResolvedStat
    modular: ResolvedStat
    stacking: ResolvedStat
    rank_locked: ResolvedStat
    total: ResolvedStat

    METADATA = {"name", "category", "type", "trigger", "is_beam", "is_battery", "compatibility", "incompatibility", "requirements", "max_rank", "max_stacks", "stacks", "is_exilus", "rank", "weapon"}
    WEAPON_TYPES = PRIMARY_TYPES | SECONDARY_TYPES | MELEE_TYPES
    BUCKETS = ("static", "conditional", "modular", "stacking", "rank_locked", "total")

    def __init__(self, upgrade: UpgradeOwner) -> None:
        self.upgrade = upgrade
        self.resolve()

    _merge_stat = staticmethod(merge_upgrade_stat)
    _merge_resolved_stat = staticmethod(merge_resolved_stat)

    def _upgrade_data(self) -> Data:
        data = self.upgrade.data
        return Data({"name": data.name, "type": data.type, "max_rank": data.max_rank, "compatibility": data.compatibility, "incompatibility": data.incompatibility, **data.runtime.with_defaults()})

    def _condition(self, weapon: Data, upgrade: Data, condition: Any) -> bool:
        if condition in self.WEAPON_TYPES:
            types = {weapon.get("type"), weapon.get("subtype"), weapon.get("category")} - {None, ""}
            if weapon.get("type") == "bow": types.add("rifle")
            return condition in types
        return bool(upgrade.get(condition, True))

    @classmethod
    def _scale(cls, value: EffectValue, multiplier: float) -> EffectValue:
        if isinstance(value, Mapping) and not isinstance(value, Dist): return {key: cls._scale(item, multiplier) for key, item in value.items()}
        if isinstance(value, bool): return value
        return value * multiplier

    def _record(self, bucket: ResolvedStat, effect: ResolvableEffect) -> None:
        merge_upgrade_stat(getattr(bucket, effect.mode), effect.stat, effect.value)
        merge_upgrade_stat(getattr(self.total, effect.mode), effect.stat, effect.value)

    def _normalize_effect(self, stat: str, effect: Data) -> ResolvableEffect:
        raw_mode = effect.get("mode", "additive")
        if raw_mode not in EFFECT_MODES: raise ValueError(f"unsupported effect mode {raw_mode!r}")
        mode = cast(EffectMode, raw_mode)

        if stat == "condition_overload":
            maximum = effect.get("stacks", {}).get("max")
            return ResolvableEffect(stat=stat, value=effect.value, bucket="static", mode=mode, scales_with_rank=True, co_max_stacks="inf" if maximum is None else maximum)

        equipped = effect.get("equipped")
        required_rank = effect.get("rank")
        condition = effect.get("when")
        stacks = effect.get("stacks")
        value = effect.value

        if equipped is not None:
            names = tuple(equipped if isinstance(equipped, list) else [equipped])
            if required_rank is not None: return ResolvableEffect(stat, value, mode, "modular", required_rank=required_rank, equipped=names, scales_with_rank=False)
            if stacks is not None: return ResolvableEffect(stat, value, mode, "modular", equipped=names, stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), scales_with_rank=True)
            return ResolvableEffect(stat, value, mode, "modular", condition=condition, equipped=names, scales_with_rank=True)

        if required_rank is not None: return ResolvableEffect(stat, value, mode, "rank_locked", required_rank=required_rank, scales_with_rank=False)
        if stacks is not None: return ResolvableEffect(stat, value, mode, "stacking", stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), scales_with_rank=True)
        if condition is None: return ResolvableEffect(stat, value, mode, "static", scales_with_rank=True)
        return ResolvableEffect(stat, value, mode, "conditional", condition=condition, scales_with_rank=True)

    def _normalize_effects(self) -> tuple[ResolvableEffect, ...]:
        return tuple(self._normalize_effect(stat, effect) for stat, raw in self.upgrade.data.stats.items() for effect in raw_effects(raw))

    def _is_effect_applicable(self, effect: ResolvableEffect, context: ResolutionContext) -> bool:
        if effect.equipped is not None and not all(name in context.equipped for name in effect.equipped): return False
        if effect.required_rank is not None and context.rank < effect.required_rank: return False
        if effect.condition is not None:
            weapon = context.weapon or Data()
            upgrade = context.upgrade or Data()
            if not self._condition(weapon, upgrade, effect.condition): return False
        return True

    def _resolve_effect(self, effect: ResolvableEffect, context: ResolutionContext) -> ResolvableEffect | None:
        return resolve_stack_scaled_effect(effect, context, scale=self._scale)

    def _aggregate_effects(self, effects: Sequence[ResolvableEffect]) -> None:
        for bucket in self.BUCKETS: setattr(self, bucket, ResolvedStat())
        for effect in effects: self._record(getattr(self, effect.bucket), effect)

    def resolve(self, weapon: Data | object | None = None, build: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = getattr(build, "data", build) or Data()
        upgrade_data = self._upgrade_data()

        max_rank = upgrade_data.get("max_rank")
        max_stacks = upgrade_data.get("max_stacks")
        rank = upgrade_data.get("rank")
        if rank is None: rank = max_rank or 0
        if max_rank is not None: rank = min(rank, max_rank)
        rank_multiplier = 1 if max_rank in {None, 0} else (rank + 1) / (max_rank + 1)
        use_defaults = set(upgrade_data) <= self.METADATA

        # Combo can stand in for unset stacks when resolving melee stacking effects.
        default_stacks = upgrade_data.get("stacks")
        if default_stacks is None:
            runtime = getattr(weapon_data, "runtime", None)
            if runtime is not None: default_stacks = runtime.get("combo")

        context = ResolutionContext(rank=rank, rank_multiplier=rank_multiplier, max_stacks=max_stacks, use_defaults=use_defaults, stacks_lookup=upgrade_data, default_stacks=default_stacks, equipped=frozenset(build_data.get("equipped", [])), weapon=weapon_data, upgrade=upgrade_data, build=build_data)
        resolve_and_aggregate(self._normalize_effects(), context, is_applicable=self._is_effect_applicable, resolve_one=self._resolve_effect, aggregate=self._aggregate_effects)
