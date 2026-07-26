from collections.abc import Mapping
from typing import Self

from ..calculators.enemy_calculator import EnemyCalculator
from ..fields.enemy import EnemyData
from ..utils.types import JsonValue


class Enemy:
    results: EnemyCalculator

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = EnemyData(data or {})
        self.results = EnemyCalculator(self)

    def set(self, context: Mapping[str, JsonValue] | None = None) -> Self:
        if context is not None: self.data.runtime.update(context)
        self.results.resolve()
        return self

    def copy(self) -> Self:
        return type(self)(self.data.copy())
