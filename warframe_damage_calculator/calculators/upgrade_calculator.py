from collections.abc import Mapping
from typing import Any

from ..data.matching import MELEE_TYPES, PRIMARY_TYPES, SECONDARY_TYPES
from ..utils.constants import DAMAGE_TYPES
from ..models.data import Data
from ..models.dist import Dist
from ..models.fields import BuildContext, ResolvedStat, SetupContext


class UpgradeCalculator:
    METADATA = {"name", "category", "type", "trigger", "is beam", "is battery", "compatibility", "incompatibility", "requirements", "max rank", "max stacks", "stacks", "is exilus", "rank", "weapon"}
    WEAPON_TYPES = PRIMARY_TYPES | SECONDARY_TYPES | MELEE_TYPES

    def __init__(self, upgrade: Any) -> None:
        self.upgrade = upgrade
        self.static = ResolvedStat()
        self.conditional = ResolvedStat()
        self.modular = ResolvedStat()
        self.stacking = ResolvedStat()
        self.rank_locked = ResolvedStat()
        self.total = ResolvedStat()
        self.resolve()

    @staticmethod
    def _key(value: Any) -> str:
        return " ".join(str(value).casefold().replace("_", " ").replace("-", " ").split())
    
    def _context(self, weapon_data: Data, build_data: Data) -> SetupContext:
        return SetupContext({
            "weapon": weapon_data.get("context", {}),
            "build": BuildContext(build_data.get("context", {})),
            "upgrade": self.upgrade.data.context,
        })

    def _value(self, context: Data, key: Any, default: Any = None) -> Any:
        key = self._key(key)
        for field, value in context.items():
            if self._key(field) == key:
                return default if value is None else value
        value = context.get(key.replace(" ", "_"), default)
        return default if value is None else value

    def _condition(self, context: SetupContext, condition: Any) -> bool:
        condition = self._key(condition)
        if condition in self.WEAPON_TYPES:
            weapon = self._key(context.weapon.get("type") or "")
            types = {weapon, self._key(context.weapon.get("category") or "")} - {""}
            if weapon == "bow": types.add("rifle")
            return condition in types
        return bool(self._value(context.upgrade, condition, True))

    def _equipped(self, context: SetupContext, required: Any) -> bool:
        required = required if isinstance(required, list) else [required]
        equipped = {self._key(name) for name in context.build.equipped}
        return all(self._key(name) in equipped for name in required)

    def _count(self, value: Any, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} on {self.upgrade.data.context.name or '<unnamed upgrade>'!r} must be a non-negative integer")
        return value

    @classmethod
    def _scale(cls, value: Any, multiplier: float) -> Any:
        return {key: cls._scale(item, multiplier) for key, item in value.items()} if isinstance(value, Mapping) else value if isinstance(value, bool) else value * multiplier

    @staticmethod
    def _add(stats: Data, stat: str, value: Any) -> None:
        if stat in DAMAGE_TYPES: stat, value = "damage", {stat: value}
        current = stats.get(stat)
        if stat == "damage": stats[stat] = Dist(current) + Dist(value)
        elif current is None: stats[stat] = value
        elif isinstance(value, bool): stats[stat] = current or value
        elif isinstance(current, Mapping) and isinstance(value, Mapping): stats[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in dict(current) | dict(value)}
        else: stats[stat] = current + value

    def _record(self, bucket: ResolvedStat, stat: str, value: Any) -> None:
        self._add(bucket, stat, value)
        self._add(self.total, stat, value)

    @staticmethod
    def _required_rank(effect: Data) -> Any:
        required_rank = effect.get("at_rank")
        condition = effect.get("when")
        return condition.get("rank") if required_rank is None and isinstance(condition, Mapping) else required_rank

    def _compute_static_stats(self, stat: str, value: Any, multiplier: float) -> None:
        self._record(self.static, stat, self._scale(value, multiplier))

    def _compute_conditional_stats(self, context: SetupContext, stat: str, value: Any, condition: Any, multiplier: float) -> None:
        if self._condition(context, condition):
            self._record(self.conditional, stat, self._scale(value, multiplier))

    def _compute_rank_locked_stats(self, bucket: ResolvedStat, stat: str, value: Any, required_rank: Any, rank: int) -> None:
        if rank >= self._count(required_rank, "required rank"):
            self._record(bucket, stat, value)

    def _compute_stacking_stats(self, context: SetupContext, bucket: ResolvedStat, stat: str, value: Any, stacks_on: Any, max_stacks: int | None, multiplier: float, defaults: bool) -> None:
        condition = self._key(stacks_on)
        stacks_value = context.upgrade.get("stacks")
        fallback = ((max_stacks or 0) if defaults else 0) if stacks_value is None else stacks_value
        stacks = self._count(self._value(context.upgrade, condition, fallback), condition)
        stacks = min(stacks, max_stacks) if max_stacks is not None else stacks
        if stacks:
            value = self._scale(value, multiplier)
            self._record(bucket, stat, value if isinstance(value, bool) else value * stacks)

    def _compute_modular_stats(self, context: SetupContext, stat: str, effect: Data, rank: int, max_stacks: int | None, multiplier: float, defaults: bool) -> None:
        if not self._equipped(context, effect.when_equipped):
            return
        condition = effect.get("when")
        required_rank = self._required_rank(effect)
        if required_rank is not None:
            self._compute_rank_locked_stats(self.modular, stat, effect.value, required_rank, rank)
        elif effect.get("stacks_on") is not None:
            self._compute_stacking_stats(context, self.modular, stat, effect.value, effect.stacks_on, max_stacks, multiplier, defaults)
        elif condition is None or self._condition(context, condition):
            self._record(self.modular, stat, self._scale(effect.value, multiplier))

    def resolve(self, weapon: Data | object | None = None, build: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = getattr(build, "data", build) or Data({"upgrades": []})
        context = self._context(weapon_data, build_data)
        self.static = ResolvedStat()
        self.conditional = ResolvedStat()
        self.modular = ResolvedStat()
        self.stacking = ResolvedStat()
        self.rank_locked = ResolvedStat()
        self.total = ResolvedStat()
        maximums = [context.upgrade.get(key) for key in ("max_rank", "max_stacks")]
        max_rank, max_stacks = (None if value is None else self._count(value, field) for value, field in zip(maximums, ("max rank", "max stacks")))
        rank_value = context.upgrade.get("rank")
        rank = self._count((max_rank or 0) if rank_value is None else rank_value, "rank")
        rank = min(rank, max_rank) if max_rank is not None else rank
        multiplier = 1 if max_rank in {None, 0} else (rank + 1) / (max_rank + 1)
        if any(isinstance(raw, Mapping) and raw.get("at_rank") is not None for effects in self.upgrade.data.stats.values() for raw in (effects if isinstance(effects, list) else [effects])):
            multiplier = 1
        defaults = {self._key(key) for key in context.upgrade} <= self.METADATA
        for stat, effects in self.upgrade.data.stats.items():
            for raw in effects if isinstance(effects, list) else [effects]:
                effect = raw if isinstance(raw, Data) and "value" in raw else Data({"value": raw})
                condition = effect.get("when")
                required_rank = self._required_rank(effect)
                if effect.get("when_equipped") is not None:
                    self._compute_modular_stats(context, stat, effect, rank, max_stacks, multiplier, defaults)
                elif required_rank is not None:
                    self._compute_rank_locked_stats(self.rank_locked, stat, effect.value, required_rank, rank)
                elif effect.get("stacks_on") is not None:
                    self._compute_stacking_stats(context, self.stacking, stat, effect.value, effect.stacks_on, max_stacks, multiplier, defaults)
                elif condition is None:
                    self._compute_static_stats(stat, effect.value, multiplier)
                else:
                    self._compute_conditional_stats(context, stat, effect.value, condition, multiplier)
