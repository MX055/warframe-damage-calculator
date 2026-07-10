from __future__ import annotations

from pathlib import Path
from typing import Any

from .access import DatabaseAccessMixin
from .construction import DatabaseConstructionMixin
from .matching import DatabaseMatchingMixin
from .normalization import normalized_key
from .paths import DEFAULT_UPGRADES_PATH, DEFAULT_WEAPONS_PATH, load_json


class WarframeDatabase(DatabaseAccessMixin, DatabaseConstructionMixin, DatabaseMatchingMixin):
    def __init__(self, weapons: dict[str, Any], upgrades: dict[str, Any]) -> None:
        self.weapons = weapons
        self.upgrades = upgrades

        self._weapon_index: dict[str, tuple[str, str]] = {}
        self._upgrade_index: dict[str, tuple[str, str]] = {}

        for section, entries in self.weapons.items():
            for name in entries:
                self._weapon_index[normalized_key(name)] = (section, name)

        for section, entries in self.upgrades.items():
            for name in entries:
                self._upgrade_index[normalized_key(name)] = (section, name)

    @classmethod
    def from_files(cls, weapons_path: str | Path = DEFAULT_WEAPONS_PATH, upgrades_path: str | Path = DEFAULT_UPGRADES_PATH) -> "WarframeDatabase":
        return cls(load_json(weapons_path), load_json(upgrades_path))

    @classmethod
    def from_folder(cls, folder: str | Path) -> "WarframeDatabase":
        folder = Path(folder)
        return cls.from_files(folder / "weapons.json", folder / "upgrades.json")


arsenal = WarframeDatabase.from_files(DEFAULT_WEAPONS_PATH, DEFAULT_UPGRADES_PATH)
