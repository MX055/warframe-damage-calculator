from typing import Any


class DatabaseEntry:
    def __init__(self, category: str, name: str, data: dict[str, Any]) -> None:
        self.category = category
        self.name = name
        self.data = data

    @property
    def is_weapon(self) -> bool:
        return self.category in {"primary", "secondary", "melee"}
