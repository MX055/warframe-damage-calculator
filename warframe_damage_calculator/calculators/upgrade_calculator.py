from collections.abc import Mapping
from typing import Any

from ..fields.upgrade import ResolvedStat
from ..loader.matching import MELEE_TYPES, PRIMARY_TYPES, SECONDARY_TYPES
from ..models.data import Data
from ..models.dist import Dist
from ..utils.constants import DAMAGE_TYPES


class UpgradeCalculator:
    METADATA = {"name", "category", "type", "trigger", "is beam", "is battery", "compatibility", "incompatibility", "requirements", "max rank", "max stacks", "stacks", "is exilus", "rank", "weapon"}
    WEAPON_TYPES = PRIMARY_TYPES | SECONDARY_TYPES | MELEE_TYPES

    def __init__(self, upgrade: Any) -> None:
        self.upgrade = upgrade
        self.resolve()

    @staticmethod
    def _key(value: Any) -> str:
        return " ".join(str(value).casefold().replace("_", " ").replace("-", " ").split())

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
            stats[stat] = {
                "value": current.get("value", 0) + value.get("value", 0),
                "max_stacks": "inf" if "inf" in maximums else max(maximums),
            }
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
        return Data({
            "name": data.name,
            "type": data.type,
            "max_rank": data.max_rank,
            "compatibility": data.compatibility,
            "incompatibility": data.incompatibility,
            **data.runtime.with_defaults(),
        })

    def _value(self, data: Data, key: Any, default: Any = None) -> Any:
        key = self._key(key)
        for field, value in data.items():
            if self._key(field) == key:
                return default if value is None else value
        value = data.get(key.replace(" ", "_"), default)
        return default if value is None else value

    def _condition(self, weapon: Data, upgrade: Data, condition: Any) -> bool:
        condition = self._key(condition)
        if condition in self.WEAPON_TYPES:
            weapon_type = self._key(weapon.get("type") or "")
            types = {weapon_type, self._key(weapon.get("subtype") or ""), self._key(weapon.get("category") or "")} - {""}
            if weapon_type == "bow":
                types.add("rifle")
            return condition in types
        return bool(self._value(upgrade, condition, True))

    def _count(self, value: Any, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} on {self.upgrade.data.name or '<unnamed upgrade>'!r} must be a non-negative integer")
        return value

    @classmethod
    def _scale(cls, value: Any, multiplier: float) -> Any:
        return {key: cls._scale(item, multiplier) for key, item in value.items()} if isinstance(value, Mapping) else value if isinstance(value, bool) else value * multiplier

    def _record(self, bucket: ResolvedStat, stat: str, value: Any) -> None:
        self._merge_stat(bucket, stat, value)
        self._merge_stat(self.total, stat, value)

    @staticmethod
    def _required_rank(effect: Data) -> Any:
        return effect.get("rank")

    @staticmethod
    def _effects(raw: Any) -> list[Data]:
        values = raw if isinstance(raw, list) else [raw]
        effects: list[Data] = []
        for value in values:
            if isinstance(value, Mapping):
                effect = value if isinstance(value, Data) else Data(value)
                if "value" not in effect:
                    raise ValueError("stat effect records require a value")
            else:
                effect = Data({"value": value})
            effects.append(effect)
        return effects

    def _compute_static_stats(self, stat: str, value: Any, multiplier: float) -> None:
        self._record(self.static, stat, self._scale(value, multiplier))

    def _compute_conditional_stats(self, weapon: Data, upgrade: Data, stat: str, value: Any, condition: Any, multiplier: float) -> None:
        if self._condition(weapon, upgrade, condition):
            self._record(self.conditional, stat, self._scale(value, multiplier))

    def _compute_rank_locked_stats(self, bucket: ResolvedStat, stat: str, value: Any, required_rank: Any, rank: int) -> None:
        if rank >= self._count(required_rank, "required rank"):
            self._record(bucket, stat, value)

    def _compute_stacking_stats(self, upgrade: Data, bucket: ResolvedStat, stat: str, value: Any, stacks_on: Any, max_stacks: int | None, multiplier: float, defaults: bool) -> None:
        condition = self._key(stacks_on)
        stacks_value = upgrade.get("stacks")
        fallback = ((max_stacks or 0) if defaults else 0) if stacks_value is None else stacks_value
        stacks = self._count(self._value(upgrade, condition, fallback), condition)
        stacks = min(stacks, max_stacks) if max_stacks is not None else stacks
        if stacks:
            value = self._scale(value, multiplier)
            self._record(bucket, stat, value if isinstance(value, bool) else value * stacks)

    def _compute_modular_stats(self, weapon: Data, build: Data, upgrade: Data, stat: str, effect: Data, rank: int, max_stacks: int | None, multiplier: float, defaults: bool) -> None:
        required = effect.equipped if isinstance(effect.equipped, list) else [effect.equipped]
        equipped = {self._key(name) for name in build.get("equipped", [])}
        if not all(self._key(name) in equipped for name in required):
            return
        condition = effect.get("when")
        required_rank = self._required_rank(effect)
        if required_rank is not None:
            self._compute_rank_locked_stats(self.modular, stat, effect.value, required_rank, rank)
        elif effect.get("stacks") is not None:
            self._compute_stacking_stats(upgrade, self.modular, stat, effect.value, effect.stacks.get("when", "stacks"), effect.stacks.get("max", max_stacks), multiplier, defaults)
        elif condition is None or self._condition(weapon, upgrade, condition):
            self._record(self.modular, stat, self._scale(effect.value, multiplier))

    def resolve(self, weapon: Data | object | None = None, build: Data | object | None = None) -> None:
        weapon_data = getattr(weapon, "data", weapon) or Data()
        build_data = getattr(build, "data", build) or Data()
        upgrade_data = self._upgrade_data()
        self.static = ResolvedStat()
        self.conditional = ResolvedStat()
        self.modular = ResolvedStat()
        self.stacking = ResolvedStat()
        self.rank_locked = ResolvedStat()
        self.total = ResolvedStat()
        maximums = [upgrade_data.get(key) for key in ("max_rank", "max_stacks")]
        max_rank, max_stacks = (None if value is None else self._count(value, field) for value, field in zip(maximums, ("max rank", "max stacks")))
        rank_value = upgrade_data.get("rank")
        rank = self._count((max_rank or 0) if rank_value is None else rank_value, "rank")
        rank = min(rank, max_rank) if max_rank is not None else rank
        multiplier = 1 if max_rank in {None, 0} else (rank + 1) / (max_rank + 1)
        if any(effect.get("rank") is not None for raw in self.upgrade.data.stats.values() for effect in self._effects(raw)):
            multiplier = 1
        defaults = {self._key(key) for key in upgrade_data} <= self.METADATA
        for stat, raw in self.upgrade.data.stats.items():
            for effect in self._effects(raw):
                if stat == "condition_overload":
                    maximum = effect.get("stacks", {}).get("max")
                    max_statuses = "inf" if maximum is None else maximum
                    if max_statuses != "inf":
                        max_statuses = self._count(max_statuses, "condition overload max stacks")
                    self._record(self.static, stat, {"value": self._scale(effect.value, multiplier), "max_stacks": max_statuses})
                    continue
                condition = effect.get("when")
                required_rank = self._required_rank(effect)
                if effect.get("equipped") is not None:
                    self._compute_modular_stats(weapon_data, build_data, upgrade_data, stat, effect, rank, max_stacks, multiplier, defaults)
                elif required_rank is not None:
                    self._compute_rank_locked_stats(self.rank_locked, stat, effect.value, required_rank, rank)
                elif effect.get("stacks") is not None:
                    self._compute_stacking_stats(upgrade_data, self.stacking, stat, effect.value, effect.stacks.get("when", "stacks"), effect.stacks.get("max", max_stacks), multiplier, defaults)
                elif condition is None:
                    self._compute_static_stats(stat, effect.value, multiplier)
                else:
                    self._compute_conditional_stats(weapon_data, upgrade_data, stat, effect.value, condition, multiplier)
