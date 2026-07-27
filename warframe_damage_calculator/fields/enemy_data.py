from typing import Literal

from ..core.data import Data
from ..utils.types import Number
from .typed_mapping import TypedMapping


FACTION_TAGS = frozenset({"grineer", "corpus", "infested", "orokin", "sentient", "stalker", "narmer", "murmur", "scaldra", "techrot", "wild"})
FACTION_TAG_ALIASES = {"grineer": "grineer", "kuva grineer": "grineer", "corpus": "corpus", "corpus amalgam": "corpus", "infested": "infested", "infestation": "infested", "infested deimos": "infested", "orokin": "orokin", "sentient": "sentient", "stalker": "stalker", "narmer": "narmer", "the murmur": "murmur", "murmur": "murmur", "scaldra": "scaldra", "techrot": "techrot", "wild": "wild"}


def faction_tag(value: object) -> str | None:
    key = " ".join(str(value or "").strip().casefold().split())
    if key in FACTION_TAGS: return key
    return FACTION_TAG_ALIASES.get(key)


class EnemyStats(Data):
    health: Number = 1
    shields: Number = 0
    armor: Number = 0
    overguard: Number = 0


class BodyPart(Data):
    type: Literal["normal", "weakpoint", "resistant"] = "normal"
    multiplier: Number = 1.0


class BodyParts(TypedMapping):
    _item_type = BodyPart


class EnemyModifiers(Data):
    pass


class EnemyRuntime(Data):
    level: Number = 1
    steel_path: bool = False
    empowered: bool = False


class EnemyData(Data):
    name: str = "Enemy"
    faction: str = ""
    base_level: Number = 1
    stats: EnemyStats = EnemyStats()
    bodyparts: BodyParts = {"body": BodyPart()}
    modifiers: EnemyModifiers = EnemyModifiers()
    runtime: EnemyRuntime = EnemyRuntime()
