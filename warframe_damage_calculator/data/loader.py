from pathlib import Path
from collections.abc import Iterator, Mapping
from typing import Any, Self

from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from .construction import DatabaseFactory
from .matching import entry_matches
from .normalization import normalize_identifier, normalize_name
from .paths import DEFAULT_UPGRADES_PATH, DEFAULT_WEAPONS_PATH, load_json
from .schema import DatabaseEntry


class WarframeDatabase:
    def __init__(self, weapons: dict[str, Any], upgrades: dict[str, Any]) -> None:
        self.weapons = weapons
        self.upgrades = upgrades
        self._factory = DatabaseFactory()
        self._entries = tuple(self._iter_database_entries())
        self._name_index = {normalize_name(entry.name): entry for entry in self._entries}

    @classmethod
    def from_files(cls, weapons_path: str | Path = DEFAULT_WEAPONS_PATH, upgrades_path: str | Path = DEFAULT_UPGRADES_PATH) -> Self:
        return cls(load_json(weapons_path), load_json(upgrades_path))

    @classmethod
    def from_folder(cls, folder: str | Path) -> Self:
        folder = Path(folder)
        return cls.from_files(folder / "weapons.json", folder / "upgrades.json")

    def get(self, name: str | None = None, *, type: str | None = None, context: Mapping[str, Any] | None = None, attribute: str | None = None) -> Any:
        if name is not None:
            entry = self._name_index.get(normalize_name(name))
            if entry is None or not entry_matches(entry, type):
                return None
            return self._apply_attribute(self._create(entry, context), attribute)

        entries = sorted((entry for entry in self._entries if entry_matches(entry, type)), key=lambda entry: normalize_name(entry.name))

        if attribute is not None and normalize_identifier(attribute) == "name":
            return [entry.name for entry in entries]

        return {entry.name: self._apply_attribute(self._create(entry, context), attribute) for entry in entries}

    def _create(self, entry: DatabaseEntry, context: Mapping[str, Any] | None) -> Weapon | Upgrade:
        item = self._factory.create(entry)
        if context is not None:
            item.context.update(context)
        return item

    def _iter_database_entries(self) -> Iterator[DatabaseEntry]:
        for category, entries in self.weapons.items():
            for name, data in entries.items():
                yield DatabaseEntry(category=category, name=name, data=data)
        for category, entries in self.upgrades.items():
            for name, data in entries.items():
                yield DatabaseEntry(category=category, name=name, data=data)

    @classmethod
    def _apply_attribute(cls, item: Weapon | Upgrade, attribute: str | None) -> Any:
        if attribute is None:
            return item
        return cls._extract_attribute(item, attribute)

    @staticmethod
    def _extract_attribute(item: Weapon | Upgrade, attribute: str) -> Any:
        key = normalize_identifier(attribute)

        if key == "name":
            return item.context.get("name")

        if isinstance(item, Upgrade):
            if key in item.context:
                return item.context.get(key)
            if key in item.stats:
                return item.stats.get(key)
            return None

        if key in item.context:
            return item.context.get(key)

        calculator = item.stats
        for state_name in ("base", "effective"):
            state = getattr(calculator, state_name, None)
            if state is not None and key in state:
                return state.get(key)

        if key in item.stats:
            return item.stats.get(key)
        if hasattr(calculator, key):
            return getattr(calculator, key)
        if hasattr(item, key):
            return getattr(item, key)
        return None


arsenal = WarframeDatabase.from_files()
