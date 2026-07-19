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
                return value
        return context.get(key.replace(" ", "_"), default)

    def _condition(self, context: SetupContext, condition: Any) -> bool:
        condition = self._key(condition)
        if condition in self.WEAPON_TYPES:
            weapon = self._key(context.weapon.get("type") or "")
            types = {weapon, self._key(context.weapon.get("category") or "")} - {""}
            if weapon == "bow": types.add("rifle")
            return condition in types
        if condition == "sacrificial set":
            return bool(context.build.sacrificial_set)
        return bool(self._value(context.upgrade, condition, True))

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

    def resolve(self, weapon: Data | object | None = None, build: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = getattr(build, "data", build) or Data({"upgrades": []})
        context = self._context(weapon_data, build_data)
        self.static = ResolvedStat()
        self.conditional = ResolvedStat()
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
                value, condition = effect.value, effect.get("when")
                required_rank = effect.get("at_rank")
                if required_rank is None and isinstance(condition, Mapping):
                    required_rank = condition.get("rank")
                if required_rank is not None:
                    if rank >= self._count(required_rank, "required rank"):
                        self._record(self.rank_locked, stat, value)
                elif effect.get("stacking", effect.get("stacks", False)):
                    condition = self._key(condition)
                    stacks_value = context.upgrade.get("stacks")
                    fallback = ((max_stacks or 0) if defaults else 0) if stacks_value is None else stacks_value
                    stacks = self._count(self._value(context.upgrade, condition, fallback), condition)
                    stacks = min(stacks, max_stacks) if max_stacks is not None else stacks
                    if stacks:
                        value = self._scale(value, multiplier)
                        value = value if isinstance(value, bool) else value * stacks
                        self._record(self.stacking, stat, value)
                elif condition is None or self._condition(context, condition):
                    value = self._scale(value, multiplier)
                    bucket = self.static if condition is None else self.conditional
                    self._record(bucket, stat, value)
