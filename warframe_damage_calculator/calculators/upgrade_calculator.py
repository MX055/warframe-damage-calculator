from collections.abc import Mapping
from typing import Any

from ..models.data import Data
from ..models.dist import Dist
from ..models.upgrade import Upgrade
from ..utils import DAMAGE_TYPES


class UpgradeCalculator:
    AUTOMATIC = {"primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol", "melee", "sacrificial set"}
    METADATA = {"name", "category", "type", "trigger", "is beam", "is battery", "compatibility", "incompatibility", "requirements", "max rank", "max stacks", "stacks", "is exilus", "rank", "weapon"}

    def __init__(self, upgrade: Upgrade) -> None:
        self.upgrade = upgrade
        self.context = self._data(upgrade.context)

    @staticmethod
    def _key(value: Any) -> str: return " ".join(str(value).casefold().replace("_", " ").replace("-", " ").split())
    @classmethod
    def _data(cls, data: Mapping[str, Any] | None) -> Data: return Data({cls._key(key): value for key, value in (data or {}).items()})

    def _count(self, value: Any, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} on {self.upgrade.context.name or '<unnamed upgrade>'!r} must be a non-negative integer")
        return value

    @classmethod
    def _scale(cls, value: Any, multiplier: float) -> Any:
        return {key: cls._scale(item, multiplier) for key, item in value.items()} if isinstance(value, Mapping) else value if isinstance(value, bool) else value * multiplier

    @staticmethod
    def _add(stats: Data, stat: str, value: Any) -> None:
        if stat in DAMAGE_TYPES: stat, value = "damage", Dist({stat: value})
        elif stat == "damage" and not isinstance(value, Dist): value = Dist(value)
        current = stats.get(stat)
        stats[stat] = value if current is None else current or value if isinstance(value, bool) else current + value

    def resolve(self) -> dict[str, Data]:
        maximums = [self.context.get(key) for key in ("max rank", "max stacks")]
        max_rank, max_stacks = (None if value is None else self._count(value, field) for value, field in zip(maximums, ("max rank", "max stacks")))
        rank = self._count(self.context.get("rank", max_rank or 0), "rank")
        rank = min(rank, max_rank) if max_rank is not None else rank
        multiplier = 1 if max_rank in {None, 0} else (rank + 1) / (max_rank + 1)
        defaults = set(self.context) <= self.AUTOMATIC | self.METADATA
        stats = Data()

        for stat, effects in self.upgrade.stats.items():
            for raw in effects if isinstance(effects, list) else [effects]:
                effect = raw if isinstance(raw, Data) and "value" in raw else Data({"value": raw})
                value, condition = effect.value, effect.when
                if isinstance(condition, Mapping) and condition.get("rank") is not None:
                    if rank >= self._count(condition["rank"], "required rank"): self._add(stats, stat, value)
                elif effect.stacking:
                    condition = self._key(condition)
                    stacks = self._count(self.context.get(condition, self.context.get("stacks", (max_stacks or 0) if defaults else 0)), condition)
                    stacks = min(stacks, max_stacks) if max_stacks is not None else stacks
                    if stacks:
                        value = self._scale(value, multiplier)
                        self._add(stats, stat, value if isinstance(value, bool) else value * stacks)
                elif condition is None or self.context.get(self._key(condition), False if self._key(condition) in self.AUTOMATIC else defaults):
                    self._add(stats, stat, self._scale(value, multiplier))

        self.context.rank = rank
        return {"stats": stats, "context": self.context}
