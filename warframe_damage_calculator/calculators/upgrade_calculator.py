"""Upgrade effect resolution: behaviour-based encoding."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, cast

from ..core.data import Data
from ..core.dist import Dist
from ..fields.upgrade import ResolvedModeStats, ResolvedStat
from ..loader.matching import MELEE_TYPES, PRIMARY_TYPES, SECONDARY_TYPES
from ..protocols import UpgradeOwner
from ..utils.types import EffectMode, Number
from .effect_resolution import ResolutionContext, ResolvableEffect, raw_effects, resolve_and_aggregate, resolve_stack_scaled_effect
from .effect_schema import (
    BEHAVIOUR_DOUBLE_FOR_BOWS,
    BEHAVIOUR_FIRST_SHOT,
    BEHAVIOUR_FROM_PUNCTURE_X_STATUS,
    BEHAVIOUR_LAST_SHOT,
    BEHAVIOUR_NEAR_YELLOW,
    BEHAVIOUR_ON_ANY_PROC,
    BEHAVIOUR_ON_CRIT,
    BEHAVIOUR_ON_HIT,
    BEHAVIOUR_ON_IMPACT_FR,
    BEHAVIOUR_STACK_RESET_CRIT_2_PLUS,
    BEHAVIOUR_STATUS_PROC_STACKS,
    BEHAVIOUR_UNIQUE_STATUS,
    COMMON_FAMILY,
    ENERVATE_RESET_CHARGES_MAX,
    behaviour_of,
    effect_family,
    normalize_mode,
    rank_scales,
)
from .magazine_position import serialize_position_effect
from .special_effects import serialize_deferred
from .stat_aggregation import merge_resolved_stat, merge_upgrade_stat

type EffectValue = Number | bool | Mapping[str, object] | Dist
DEFERRED = frozenset({"magazine_position", "stacking_reset", "application_chance", "conversions"})


class UpgradeCalculator:
    static: ResolvedStat
    conditional: ResolvedStat
    modular: ResolvedStat
    stacking: ResolvedStat
    rank_locked: ResolvedStat
    total: ResolvedStat

    METADATA = {"name", "category", "type", "trigger", "is_beam", "is_battery", "compatibility", "incompatibility", "requirements", "max_rank", "max_stacks", "stacks", "is_exilus", "rank", "weapon", "combos"}
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
        if isinstance(value, (bool, str)): return value
        return value * multiplier

    def _record_family(self, resolved: ResolvedStat, effect: ResolvableEffect) -> None:
        current = resolved.multiplicative_families.get(effect.family)
        if not isinstance(current, ResolvedModeStats):
            current = ResolvedModeStats(current) if isinstance(current, Mapping) else ResolvedModeStats()
            resolved.multiplicative_families[effect.family] = current
        merge_upgrade_stat(current, effect.stat, effect.value)

    def _record(self, bucket: ResolvedStat, effect: ResolvableEffect) -> None:
        if effect.bucket == "magazine_position":
            entry = serialize_position_effect(stat=effect.stat, value=effect.value, when=effect.condition or "", exclude=effect.exclude, family=effect.family, mode=effect.mode)
            self.total.magazine_position = [*(self.total.magazine_position or []), entry]
            return
        if effect.bucket in {"stacking_reset", "application_chance", "conversions"}:
            payload = serialize_deferred(effect.value if isinstance(effect.value, Mapping) else {"value": effect.value})
            setattr(self.total, effect.bucket, [*(getattr(self.total, effect.bucket) or []), payload])
            return
        if effect.mode == "proportional" and effect.family != COMMON_FAMILY:
            self._record_family(bucket, effect)
            self._record_family(self.total, effect)
            return
        merge_upgrade_stat(getattr(bucket, effect.mode), effect.stat, effect.value)
        merge_upgrade_stat(getattr(self.total, effect.mode), effect.stat, effect.value)

    @staticmethod
    def _exclude_flags(effect: Data) -> tuple[str, ...]:
        exclude = effect.get("exclude")
        if exclude is None: return ()
        return tuple(exclude) if isinstance(exclude, list) else (str(exclude),)

    def _normalize_effect(self, stat: str, effect: Data) -> ResolvableEffect:
        mode = cast(EffectMode, normalize_mode(effect.get("mode")))
        family = effect_family(effect)
        scales = rank_scales(effect)
        behaviour = behaviour_of(effect)
        value = effect.value
        exclude = self._exclude_flags(effect)
        equipped = effect.get("equipped")
        required_rank = effect.get("rank")
        condition = effect.get("when")
        stacks = effect.get("stacks")

        if behaviour == BEHAVIOUR_FIRST_SHOT:
            if family == COMMON_FAMILY: family = "chamber"
            return ResolvableEffect(stat, value, "proportional", "magazine_position", condition="first_shot", exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)
        if behaviour == BEHAVIOUR_LAST_SHOT:
            if family == COMMON_FAMILY: family = "charge"
            return ResolvableEffect(stat, value, "proportional", "magazine_position", condition="last_shot", exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_STACK_RESET_CRIT_2_PLUS:
            if stat != "crit_chance": raise ValueError("STACK_RESET_CRIT_2_PLUS requires crit_chance")
            payload = {"stat": "crit_chance", "value": value, "mode": "flat", "behaviour": behaviour, "after_max": ENERVATE_RESET_CHARGES_MAX}
            return ResolvableEffect(stat="stacking_reset", value=payload, bucket="stacking_reset", mode="proportional", scales_with_rank=False, behaviour=behaviour)

        if behaviour == BEHAVIOUR_ON_CRIT:
            if stat != "slash_proc": raise ValueError("ON_CRIT requires slash_proc")
            return ResolvableEffect(stat="application_chance", value={"stat": "slash_proc", "value": value, "behaviour": behaviour, "chance": value}, bucket="application_chance", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_ON_IMPACT_FR:
            if stat != "slash_proc": raise ValueError("ON_IMPACT_DOUBLE_BELOW_2_5_FR requires slash_proc")
            return ResolvableEffect(stat="application_chance", value={"stat": "slash_proc", "value": value, "behaviour": behaviour, "chance": value}, bucket="application_chance", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_ON_ANY_PROC:
            if stat != "random_proc": raise ValueError("ON_ANY_PROC requires random_proc")
            return ResolvableEffect(stat="application_chance", value={"stat": "random_proc", "value": value, "behaviour": behaviour, "chance": value}, bucket="application_chance", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_ON_HIT:
            if stat != "crit_chance": raise ValueError("ON_HIT requires crit_chance")
            return ResolvableEffect(stat="application_chance", value={"stat": "crit_chance", "value": value, "behaviour": behaviour, "mode": "flat"}, bucket="application_chance", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_NEAR_YELLOW:
            if stat != "duplicated_hit": raise ValueError("NEAR_YELLOW requires duplicated_hit")
            return ResolvableEffect(stat="application_chance", value={"stat": "duplicated_hit", "value": value, "behaviour": behaviour}, bucket="application_chance", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_FROM_PUNCTURE_X_STATUS:
            return ResolvableEffect(stat="conversions", value={"stat": stat, "value": value, "behaviour": behaviour, "mode": "flat"}, bucket="conversions", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if behaviour == BEHAVIOUR_UNIQUE_STATUS:
            # CO amount lives on proportional.condition_overload; product folding happens at apply time.
            if isinstance(stacks, Mapping) and stacks.get("when") not in {None, "status_type"}:
                return ResolvableEffect(stat="condition_overload", value=value, bucket="stacking", stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), scales_with_rank=scales, co_max_stacks="inf", behaviour=behaviour)
            maximum = stacks.get("max") if isinstance(stacks, Mapping) else None
            return ResolvableEffect(stat="condition_overload", value=value, bucket="static", mode="proportional", scales_with_rank=scales, co_max_stacks="inf" if maximum is None else maximum, behaviour=behaviour)

        if behaviour == BEHAVIOUR_STATUS_PROC_STACKS:
            status = effect.get("status")
            if not status: raise ValueError("STATUS_PROC_STACKS requires status")
            maximum = stacks.get("max") if isinstance(stacks, Mapping) else None
            if maximum is None: raise ValueError("STATUS_PROC_STACKS requires stacks.max")
            payload = {"value": value, "stat": stat, "status": status, "max_stacks": maximum, "mode": "proportional"}
            if isinstance(stacks, Mapping) and stacks.get("duration") is not None: payload["duration"] = stacks["duration"]
            return ResolvableEffect(stat="status_effect_stacks", value=payload, bucket="static", mode="proportional", scales_with_rank=scales, behaviour=behaviour)

        if equipped is not None:
            names = tuple(equipped if isinstance(equipped, list) else [equipped])
            if required_rank is not None: return ResolvableEffect(stat, value, mode, "modular", required_rank=required_rank, equipped=names, exclude=exclude, family=family, scales_with_rank=False, behaviour=behaviour)
            if stacks is not None: return ResolvableEffect(stat, value, mode, "modular", equipped=names, stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)
            return ResolvableEffect(stat, value, mode, "modular", condition=condition, equipped=names, exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)

        if required_rank is not None: return ResolvableEffect(stat, value, mode, "rank_locked", required_rank=required_rank, exclude=exclude, family=family, scales_with_rank=False, behaviour=behaviour)
        if stacks is not None: return ResolvableEffect(stat, value, mode, "stacking", stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)
        if behaviour == BEHAVIOUR_DOUBLE_FOR_BOWS:
            return ResolvableEffect(stat, value, mode, "conditional", condition="bow", exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)
        if condition is None: return ResolvableEffect(stat, value, mode, "static", exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)
        return ResolvableEffect(stat, value, mode, "conditional", condition=condition, exclude=exclude, family=family, scales_with_rank=scales, behaviour=behaviour)

    def _normalize_effects(self) -> tuple[ResolvableEffect, ...]:
        effects: list[ResolvableEffect] = []
        for stat, raw in self.upgrade.data.stats.items():
            for effect in raw_effects(raw):
                normalized = self._normalize_effect(stat, effect)
                if behaviour_of(effect) == BEHAVIOUR_DOUBLE_FOR_BOWS:
                    base = replace(normalized, behaviour=None, condition=None, bucket="static")
                    bow = replace(normalized, bucket="conditional", condition="bow")
                    effects.extend((base, bow))
                else:
                    effects.append(normalized)
        return tuple(effects)

    def _is_effect_applicable(self, effect: ResolvableEffect, context: ResolutionContext) -> bool:
        if effect.equipped is not None and not all(name in context.equipped for name in effect.equipped): return False
        if effect.required_rank is not None and context.rank < effect.required_rank: return False
        if effect.bucket in DEFERRED: return True
        if effect.condition is not None:
            if not self._condition(context.weapon or Data(), context.upgrade or Data(), effect.condition): return False
        return True

    def _resolve_effect(self, effect: ResolvableEffect, context: ResolutionContext) -> ResolvableEffect | None:
        if effect.bucket == "stacking_reset":
            payload = dict(effect.value)
            payload["after"] = float(payload.get("after_max") or ENERVATE_RESET_CHARGES_MAX) * context.rank_multiplier
            return replace(effect, value=payload)
        if effect.bucket in {"application_chance", "conversions"}:
            payload = dict(effect.value)
            if effect.scales_with_rank:
                if "chance" in payload: payload["chance"] = self._scale(payload["chance"], context.rank_multiplier)
                else: payload["value"] = self._scale(payload["value"], context.rank_multiplier)
            return replace(effect, value=payload)
        return resolve_stack_scaled_effect(effect, context, scale=self._scale)

    def _aggregate_effects(self, effects: Sequence[ResolvableEffect]) -> None:
        for bucket in self.BUCKETS: setattr(self, bucket, ResolvedStat())
        for effect in effects:
            if effect.bucket in DEFERRED:
                self._record(self.total, effect)
                continue
            self._record(getattr(self, effect.bucket), effect)

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
        default_stacks = upgrade_data.get("stacks")
        if default_stacks is None:
            runtime = getattr(weapon_data, "runtime", None)
            if runtime is not None: default_stacks = runtime.get("combo")
        context = ResolutionContext(rank=rank, rank_multiplier=rank_multiplier, max_stacks=max_stacks, use_defaults=use_defaults, stacks_lookup=upgrade_data, default_stacks=default_stacks, equipped=frozenset(build_data.get("equipped", [])), weapon=weapon_data, upgrade=upgrade_data, build=build_data)
        resolve_and_aggregate(self._normalize_effects(), context, is_applicable=self._is_effect_applicable, resolve_one=self._resolve_effect, aggregate=self._aggregate_effects)
