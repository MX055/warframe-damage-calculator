from collections.abc import Mapping
from typing import Any


class DatabaseEntry:
    def __init__(self, category: str, data: Mapping[str, Any], match_types: set[str] | None = None, identifier: str | None = None) -> None:
        self.category = category
        self.data = dict(data)
        self.match_types = match_types or set()
        self.identifier = identifier

    @property
    def name(self) -> str:
        return self.identifier or str(self.data["name"])

    @property
    def is_weapon(self) -> bool:
        return self.category in {"primary", "secondary", "melee"}

    @property
    def is_upgrade(self) -> bool:
        return self.category in {"mod", "arcane"}

    @property
    def is_enemy(self) -> bool:
        return self.category == "enemy"
