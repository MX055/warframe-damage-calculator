from collections.abc import Mapping

from ..models.data import Data
from ..utils.types import JsonValue
from .calculated import AverageStats, CalculatedStats
from .upgrade import ResolvedStat
from .weapon_data import Attack


class AttackResult(Data):
    name: str = ""
    attack: Attack = Attack()
    build: ResolvedStat = ResolvedStat()
    base: CalculatedStats = CalculatedStats()
    modded: CalculatedStats = CalculatedStats()
    effective: CalculatedStats = CalculatedStats()
    average: AverageStats = AverageStats()
    final: AverageStats = AverageStats()
    children: list[str] = []

    @property
    def trigger(self) -> str | None:
        return self.attack.trigger

    @property
    def delivery(self) -> str | None:
        return self.attack.delivery

    @property
    def aoe(self) -> bool:
        return self.attack.aoe


class AttackResults(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, AttackResult):
            value = AttackResult(value)
        super().__setitem__(key, value)
