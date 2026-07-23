from ..models.data import Data
from ..models.dist import Dist
from .calculated import AverageStats, CalculatedStats, ModdedStats
from .evolution import ResolvedEvolutionStat
from .upgrade import ResolvedStat
from .weapon_data import Attack


class AttackResult(Data):
    name: str = ""
    attack: Attack = Attack()
    build: ResolvedStat = ResolvedStat()
    evolutions: ResolvedEvolutionStat = ResolvedEvolutionStat()
    original_damage: Dist = Dist()
    base: CalculatedStats = CalculatedStats()
    modded: ModdedStats = ModdedStats()
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
