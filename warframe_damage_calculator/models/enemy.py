from collections.abc import Mapping
from typing import Self

from ..fields.enemy import EnemyData
from ..utils.types import JsonValue


class Enemy:
    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = EnemyData(data or {})

    def copy(self) -> Self:
        return type(self)(self.data.copy())
