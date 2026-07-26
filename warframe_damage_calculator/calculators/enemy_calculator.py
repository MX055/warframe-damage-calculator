from math import floor

from ..fields.enemy import EnemyStats
from ..protocols import EnemyOwner


type Scaling = tuple[float, float, float, float]
STANDARD_HEALTH_SCALING: Scaling = (0.015, 2.0, 10.733, 0.5)
STANDARD_SHIELD_SCALING: Scaling = (0.02, 1.75, 2.0, 0.75)
ARMOR_SCALING: Scaling = (0.005, 1.75, 0.4, 0.75)
OVERGUARD_SCALING: Scaling = (0.0015, 4.0, 260.0, 0.9)
STANDARD_FACTIONS = ("?", "Anarch", "Duviri", "Narmer", "Neutral", "Objects", "Predator", "Prey", "Scaldra", "Sentient", "Stalker", "Techrot", "Tenno", "The Murmur", "Unknown")
HEALTH_SCALING: dict[str, Scaling] = {faction: STANDARD_HEALTH_SCALING for faction in STANDARD_FACTIONS} | {
    "Grineer": (0.015, 2.12, 10.733, 0.72),
    "Kuva Grineer": (0.015, 2.12, 10.733, 0.72),
    "Corpus": (0.015, 2.12, 13.416, 0.55),
    "Corpus Amalgam": (0.015, 2.12, 13.416, 0.55),
    "Infestation": (0.0225, 2.12, 16.1, 0.72),
    "Infested": (0.0225, 2.12, 16.1, 0.72),
    "Infested Deimos": (0.0225, 2.12, 16.1, 0.72),
    "Orokin": (0.015, 2.1, 10.733, 0.685),
}
SHIELD_SCALING: dict[str, Scaling] = {faction: STANDARD_SHIELD_SCALING for faction in STANDARD_FACTIONS} | {
    "Orokin": STANDARD_SHIELD_SCALING,
    "Grineer": (0.02, 1.75, 1.6, 0.75),
    "Kuva Grineer": (0.02, 1.75, 1.6, 0.75),
    "Corpus": (0.02, 1.76, 2.0, 0.76),
    "Corpus Amalgam": (0.02, 1.76, 2.0, 0.76),
    "Infestation": (0.02, 1.75, 1.6, 0.75),
    "Infested": (0.02, 1.75, 1.6, 0.75),
    "Infested Deimos": (0.02, 1.75, 1.6, 0.75),
}
STEEL_PATH_MULTIPLIER = 2.5
EMPOWERED_MULTIPLIER = 2.5
ARMOR_CAP = 2700


def smoothstep(delta: float, start: float, end: float) -> float:
    if delta < start: return 0.0
    if delta > end: return 1.0
    transition = (delta - start) / (end - start)
    return 3 * transition ** 2 - 2 * transition ** 3


def level_multiplier(delta: float, scaling: Scaling, start: float = 70, end: float = 80) -> float:
    first_coefficient, first_exponent, second_coefficient, second_exponent = scaling
    first = first_coefficient * delta ** first_exponent
    second = second_coefficient * delta ** second_exponent
    transition = smoothstep(delta, start, end)
    return 1 + first + (second - first) * transition


class EnemyCalculator:
    def __init__(self, enemy: EnemyOwner) -> None:
        self.enemy = enemy
        self._effective = EnemyStats()
        self._inputs_fingerprint: object | None = None

    def _fingerprint(self) -> tuple:
        data = self.enemy.data
        return (data.faction, data.base_level, tuple(data.stats.items()), tuple(data.runtime.items()))

    @property
    def effective(self) -> EnemyStats:
        if self._fingerprint() != self._inputs_fingerprint: self.resolve()
        return self._effective

    def resolve(self) -> None:
        data = self.enemy.data
        delta = max(float(data.runtime.level) - float(data.base_level), 0.0)
        health_multiplier = level_multiplier(delta, HEALTH_SCALING[data.faction])
        shield_multiplier = level_multiplier(delta, SHIELD_SCALING[data.faction])
        armor_multiplier = level_multiplier(delta, ARMOR_SCALING)
        overguard_multiplier = level_multiplier(delta, OVERGUARD_SCALING, 45, 50)
        steel_path_multiplier = STEEL_PATH_MULTIPLIER if data.runtime.steel_path else 1.0
        empowered_multiplier = EMPOWERED_MULTIPLIER if data.runtime.empowered else 1.0
        self._effective = EnemyStats({
            "health": round(float(data.stats.health) * health_multiplier * steel_path_multiplier * empowered_multiplier, 2),
            "shields": round(float(data.stats.shields) * shield_multiplier * steel_path_multiplier * empowered_multiplier, 2),
            "armor": min(floor(float(data.stats.armor) * armor_multiplier * steel_path_multiplier), ARMOR_CAP),
            "overguard": round(float(data.stats.overguard) * overguard_multiplier, 2),
        })
        self._inputs_fingerprint = self._fingerprint()
