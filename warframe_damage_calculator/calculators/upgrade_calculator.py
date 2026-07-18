from collections.abc import Mapping
from typing import Any

from ..utils.constants import DAMAGE_TYPES
from ..models.data import Data
from ..models.dist import Dist


class UpgradeCalculator:
    AUTOMATIC = {"primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol", "melee", "sacrificial set"}
    METADATA = {"name", "category", "type", "trigger", "is beam", "is battery", "compatibility", "incompatibility", "requirements", "max rank", "max stacks", "stacks", "is exilus", "rank", "weapon"}

    def __init__(self, upgrade: Any) -> None:
        self.upgrade = upgrade
        self.static = Data()
        self.conditional = Data()
        self.stacking = Data()
        self.rank_locked = Data()
        self.total = Data()
        self.resolve()

    @staticmethod
    def _key(value: Any) -> str:
        return " ".join(str(value).casefold().replace("_", " ").replace("-", " ").split())
    
    @classmethod
    def _data(cls, data: Mapping[str, Any] | None) -> Data:
        return Data({cls._key(key): value for key, value in (data or {}).items()})

    def _context(self, weapon_data: Data, build_data: Data) -> Data:
        context = self._data(weapon_data.get("context"))
        weapon = self._key(context.get("type") or context.get("weapon") or "")
        types = {weapon, self._key(context.get("category") or "")} - {""}
        if weapon == "bow": types.add("rifle")
        context.update({key: key in types for key in self.AUTOMATIC - {"sacrificial set"}})
        context.weapon = weapon
        names = {self._key(upgrade.context.get("name", "")) for upgrade in build_data.get("upgrades", [])}
        context["sacrificial set"] = {"sacrificial pressure", "sacrificial steel"}.issubset(names)
        return context | self._data(self.upgrade.data.context)

    def _count(self, value: Any, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} on {self.upgrade.data.context.name or '<unnamed upgrade>'!r} must be a non-negative integer")
        return value

    @classmethod
    def _scale(cls, value: Any, multiplier: float) -> Any:
        return {key: cls._scale(item, multiplier) for key, item in value.items()} if isinstance(value, dict) else value if isinstance(value, bool) else value * multiplier

    @staticmethod
    def _add(stats: Data, stat: str, value: Any) -> None:
        if stat in DAMAGE_TYPES: stat, value = "damage", {stat: value}
        current = stats.get(stat)
        if current is None: stats[stat] = value
        elif isinstance(value, bool): stats[stat] = current or value
        elif isinstance(current, dict) and isinstance(value, dict): stats[stat] = {key: current.get(key, 0) + value.get(key, 0) for key in current | value}
        else: stats[stat] = current + value

    @staticmethod
    def _combine_damage(stats: Data) -> None:
        if "damage" in stats:
            stats.damage = Dist(stats.damage)

    def _record(self, bucket: Data, stat: str, value: Any) -> None:
        self._add(bucket, stat, value)
        self._add(self.total, stat, value)

    def resolve(self, weapon: Data | object | None = None, build: Data | object | None = None) -> dict[str, Data]:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = getattr(build, "data", build) or Data({"upgrades": []})
        context = self._context(weapon_data, build_data)
        self.static = Data()
        self.conditional = Data()
        self.stacking = Data()
        self.rank_locked = Data()
        self.total = Data()
        maximums = [context.get(key) for key in ("max rank", "max stacks")]
        max_rank, max_stacks = (None if value is None else self._count(value, field) for value, field in zip(maximums, ("max rank", "max stacks")))
        rank = self._count(context.get("rank", max_rank or 0), "rank")
        rank = min(rank, max_rank) if max_rank is not None else rank
        multiplier = 1 if max_rank in {None, 0} else (rank + 1) / (max_rank + 1)
        if any(isinstance(raw, dict) and raw.get("at_rank") is not None for effects in self.upgrade.data.stats.values() for raw in (effects if isinstance(effects, list) else [effects])):
            multiplier = 1
        defaults = set(context) <= self.AUTOMATIC | self.METADATA
        for stat, effects in self.upgrade.data.stats.items():
            for raw in effects if isinstance(effects, list) else [effects]:
                effect = raw if isinstance(raw, Data) and "value" in raw else Data({"value": raw})
                value, condition = effect.value, effect.get("when")
                required_rank = effect.get("at_rank")
                if required_rank is None and isinstance(condition, dict):
                    required_rank = condition.get("rank")
                if required_rank is not None:
                    if rank >= self._count(required_rank, "required rank"):
                        self._record(self.rank_locked, stat, value)
                elif effect.get("stacking", effect.get("stacks", False)):
                    condition = self._key(condition)
                    stacks = self._count(context.get(condition, context.get("stacks", (max_stacks or 0) if defaults else 0)), condition)
                    stacks = min(stacks, max_stacks) if max_stacks is not None else stacks
                    if stacks:
                        value = self._scale(value, multiplier)
                        value = value if isinstance(value, bool) else value * stacks
                        self._record(self.stacking, stat, value)
                elif condition is None or context.get(self._key(condition), self._key(condition) not in self.AUTOMATIC):
                    value = self._scale(value, multiplier)
                    bucket = self.static if condition is None else self.conditional
                    self._record(bucket, stat, value)

        context.rank = rank
        for bucket in (self.static, self.conditional, self.stacking, self.rank_locked, self.total):
            self._combine_damage(bucket)
        return {"stats": self.total, "context": context}
