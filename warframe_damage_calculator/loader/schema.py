from collections.abc import Mapping
from typing import Any


class DatabaseEntry:
    def __init__(self, category: str, name: str, data: Mapping[str, Any], match_types: set[str] | None = None) -> None:
        self.category = category
        self.name = name
        self.data = dict(data)
        self.match_types = match_types or set()

    @property
    def is_weapon(self) -> bool:
        return self.category in {"primary", "secondary", "melee"}
