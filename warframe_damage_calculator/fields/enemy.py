from collections.abc import Mapping
from typing import Literal

from ..core.data import Data
from ..utils.types import JsonValue, Number


class EnemyStats(Data):
    health: Number = 1
    shields: Number = 0
    armor: Number = 0
    overguard: Number = 0


class BodyPart(Data):
    type: Literal["normal", "weakpoint", "resistant"] = "normal"
    multiplier: Number = 1.0


class BodyParts(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, BodyPart): value = BodyPart(value)
        super().__setitem__(key, value)


class EnemyModifiers(Data):
    pass


class EnemyRuntime(Data):
    level: Number = 1
    steel_path: bool = False
    empowered: bool = False


class EnemyData(Data):
    name: str = "Enemy"
    faction: str = "Unknown"
    base_level: Number = 1
    stats: EnemyStats = EnemyStats()
    bodyparts: BodyParts = {"body": BodyPart()}
    modifiers: EnemyModifiers = {}
    runtime: EnemyRuntime = EnemyRuntime()
