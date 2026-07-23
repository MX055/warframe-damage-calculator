from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from ..fields.upgrade import ResolvedStat
from ..loader.matching import MELEE_TYPES, PRIMARY_TYPES, SECONDARY_TYPES
from ..models.data import Data
from ..models.dist import Dist
from ..protocols import UpgradeOwner
from ..utils.constants import DAMAGE_TYPES, EFFECT_MODES
from ..utils.types import EffectMode, Number


type EffectBucket = Literal["static", "conditional", "modular", "stacking", "rank_locked"]
type EffectValue = Number | bool | Mapping[str, object] | Dist


@dataclass(frozen=True, slots=True)
class _Effect:
    stat: str
    value: EffectValue
    bucket: EffectBucket
    mode: EffectMode = "additive"
    required_rank: int | None = None
    condition: str | None = None
    equipped: tuple[str, ...] | None = None
    stacks_on: str | None = None
    max_stacks: int | None = None
    scales_with_rank: bool = True
    co_max_stacks: int | str | None = None


@dataclass(frozen=True, slots=True)
class _ResolutionContext:
    weapon: Data
    build: Data
    upgrade: Data
    rank: int
    rank_multiplier: float
    max_stacks: int | None
    use_defaults: bool


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

    @staticmethod
    def _merge_stat(stats: Data, stat: str, value: Any) -> None:
        if stat in DAMAGE_TYPES:
            stat, value = "damage", {stat: value}
        current = stats.get(stat)
        if stat == "damage":
            if not isinstance(current, Dist):
                current = Dist(current or {})
            if not isinstance(value, Dist):
                value = Dist(value)
            stats[stat] = current + value
        elif stat == "condition_overload":
            current = current or {}
            maximums = {current.get("max_stacks", 0), value.get("max_stacks", 0)}
            stats[stat] = {"value": current.get("value", 0) + value.get("value", 0), "max_stacks": "inf" if "inf" in maximums else max(maximums),}
        elif current is None:
            stats[stat] = value
        elif isinstance(value, bool):
            stats[stat] = current or value
        elif isinstance(current, Mapping) and isinstance(value, Mapping):
            stats[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in dict(current) | dict(value)}
        else:
            stats[stat] = current + value

    def _upgrade_data(self) -> Data:
        data = self.upgrade.data
        return Data({"name": data.name, "type": data.type, "max_rank": data.max_rank, "compatibility": data.compatibility, "incompatibility": data.incompatibility, **data.runtime.with_defaults()})

    def _condition(self, weapon: Data, upgrade: Data, condition: Any) -> bool:
        if condition in self.WEAPON_TYPES:
            types = {weapon.get("type"), weapon.get("subtype"), weapon.get("category")} - {None, ""}
            if weapon.get("type") == "bow":
                types.add("rifle")
            return condition in types
        return bool(upgrade.get(condition, True))

    @classmethod
    def _scale(cls, value: EffectValue, multiplier: float) -> EffectValue:
        if isinstance(value, Mapping) and not isinstance(value, Dist):
            return {key: cls._scale(item, multiplier) for key, item in value.items()}
        if isinstance(value, bool):
            return value
        return value * multiplier

    def _record(self, bucket: ResolvedStat, effect: _Effect) -> None:
        self._merge_stat(getattr(bucket, effect.mode), effect.stat, effect.value)
        self._merge_stat(getattr(self.total, effect.mode), effect.stat, effect.value)

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

        if stat == "condition_overload":
            maximum = effect.get("stacks", {}).get("max")
            return _Effect(stat=stat, value=effect.value, bucket="static", mode=mode, scales_with_rank=True, co_max_stacks="inf" if maximum is None else maximum)

        equipped = effect.get("equipped")
        required_rank = effect.get("rank")
        condition = effect.get("when")
        stacks = effect.get("stacks")
        value = effect.value

        if equipped is not None:
            names = tuple(equipped if isinstance(equipped, list) else [equipped])
            if required_rank is not None:
                return _Effect(stat, value, "modular", mode=mode, required_rank=required_rank, equipped=names, scales_with_rank=False)
            if stacks is not None:
                return _Effect(stat, value, "modular", mode=mode, equipped=names, stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), scales_with_rank=True)
            return _Effect(stat, value, "modular", mode=mode, condition=condition, equipped=names, scales_with_rank=True)

        if required_rank is not None:
            return _Effect(stat, value, "rank_locked", mode=mode, required_rank=required_rank, scales_with_rank=False)
        if stacks is not None:
            return _Effect(stat, value, "stacking", mode=mode, stacks_on=stacks.get("when", "stacks"), max_stacks=stacks.get("max"), scales_with_rank=True)
        if condition is None:
            return _Effect(stat, value, "static", mode=mode, scales_with_rank=True)
        return _Effect(stat, value, "conditional", mode=mode, condition=condition, scales_with_rank=True)

    def _normalize_effects(self) -> tuple[_Effect, ...]:
        return tuple(self._normalize_effect(stat, effect) for stat, raw in self.upgrade.data.stats.items() for effect in self._raw_effects(raw))

    def _stack_count(self, effect: _Effect, context: _ResolutionContext) -> int:
        effect_max = effect.max_stacks if effect.max_stacks is not None else context.max_stacks
        stacks_value = context.upgrade.get("stacks")
        if stacks_value is None:
            fallback = (effect_max or 0) if context.use_defaults else 0
        else:
            fallback = stacks_value
        stacks = context.upgrade.get(effect.stacks_on, fallback)
        return min(stacks, effect_max) if effect_max is not None else stacks

    def _is_effect_applicable(self, effect: _Effect, context: _ResolutionContext) -> bool:
        if effect.equipped is not None:
            equipped_names = set(context.build.get("equipped", []))
            if not all(name in equipped_names for name in effect.equipped):
                return False
        if effect.required_rank is not None and context.rank < effect.required_rank:
            return False
        if effect.condition is not None and not self._condition(context.weapon, context.upgrade, effect.condition):
            return False
        return True

    def _resolve_effect(self, effect: _Effect, context: _ResolutionContext) -> _Effect | None:
        stacks = 1
        if effect.stacks_on is not None:
            stacks = self._stack_count(effect, context)
            if not stacks:
                return None

        value = self._scale(effect.value, context.rank_multiplier) if effect.scales_with_rank else effect.value
        if effect.stat == "condition_overload":
            value = {"value": value, "max_stacks": effect.co_max_stacks}
        elif effect.stacks_on is not None and not isinstance(value, bool):
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

    def _aggregate_effects(self, effects: Iterable[_Effect]) -> None:
        for bucket in self.BUCKETS:
            setattr(self, bucket, ResolvedStat())
        for effect in effects:
            self._record(getattr(self, effect.bucket), effect)

    def resolve(self, weapon: Data | object | None = None, build: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = getattr(build, "data", build) or Data()
        upgrade_data = self._upgrade_data()

        max_rank = upgrade_data.get("max_rank")
        max_stacks = upgrade_data.get("max_stacks")
        rank = upgrade_data.get("rank")
        if rank is None:
            rank = max_rank or 0
        if max_rank is not None:
            rank = min(rank, max_rank)
        rank_multiplier = 1 if max_rank in {None, 0} else (rank + 1) / (max_rank + 1)
        use_defaults = set(upgrade_data) <= self.METADATA

        context = _ResolutionContext(weapon=weapon_data, build=build_data, upgrade=upgrade_data, rank=rank, rank_multiplier=rank_multiplier, max_stacks=max_stacks, use_defaults=use_defaults)
        effects = self._normalize_effects()
        applicable = self._resolve_effects(effects, context)
        self._aggregate_effects(applicable)
