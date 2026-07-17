from pathlib import Path
from collections.abc import Iterator
from typing import Any, Literal, overload, Self

from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from ..models.primary import Primary
from ..models.secondary import Secondary
from ..models.melee import Melee
from .construction import DatabaseFactory
from .matching import entry_matches
from .normalization import normalize_identifier, normalize_name
from .paths import DEFAULT_UPGRADES_PATH, DEFAULT_WEAPONS_PATH, load_json
from .schema import DatabaseEntry

type DatabaseItem = Weapon | Upgrade
type WeaponItem = Primary | Secondary | Melee
type PrimaryFilter = Literal["primary", "primaries", "rifle", "bow", "shotgun", "sniper"]
type SecondaryFilter = Literal["secondary", "secondaries", "pistol", "pistols"]
type MeleeFilter = Literal["melee", "melees"]
type WeaponFilter = Literal["weapon", "weapons"]
type UpgradeFilter = Literal["upgrade", "upgrades", "mod", "mods", "arcane", "arcanes"]


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
    
    @overload
    def get(self, name: str) -> WeaponItem | None: ...

    @overload
    def get(self, name: str) -> Upgrade | None: ...

    @overload
    def get(self, name: str, *, type: WeaponFilter, context: dict[str, Any] | None = None, attribute: None = None) -> WeaponItem | None: ...

    @overload
    def get(self, name: str, *, type: UpgradeFilter, context: dict[str, Any] | None = None, attribute: None = None) -> Upgrade | None: ...

    @overload
    def get(self, name: None = None, *, type: str | None = None, context: dict[str, Any] | None = None, attribute: Literal["name"]) -> list[str]: ...

    @overload
    def get(self, name: None = None, *, type: WeaponFilter, context: dict[str, Any] | None = None, attribute: None = None) -> dict[str, WeaponItem]: ...

    @overload
    def get(self, name: None = None, *, type: UpgradeFilter, context: dict[str, Any] | None = None, attribute: None = None) -> dict[str, Upgrade]: ...

    @overload
    def get(self, name: None = None, *, type: str | None = None, context: dict[str, Any] | None = None, attribute: str) -> list[str] | dict[str, object | None]: ...

    def get(self, name: str | None = None, *, type: str | None = None, context: dict[str, Any] | None = None, attribute: str | None = None) -> DatabaseItem | None | list[str] | dict[str, DatabaseItem] | dict[str, object | None]:
        if name is not None:
            entry = self._name_index.get(normalize_name(name))
            if entry is None or not entry_matches(entry, type):
                return None
            return self._apply_attribute(self._create(entry, context), attribute)

        entries = sorted((entry for entry in self._entries if entry_matches(entry, type)), key=lambda entry: normalize_name(entry.name))

        if attribute is not None and normalize_identifier(attribute) == "name":
            return [entry.name for entry in entries]

        return {entry.name: self._apply_attribute(self._create(entry, context), attribute) for entry in entries}

    def _create(self, entry: DatabaseEntry, context: dict[str, Any] | None) -> DatabaseItem:
        item = self._factory.create(entry)
        if context is not None:
            item.data.context.update(context)
        return item

    def _iter_database_entries(self) -> Iterator[DatabaseEntry]:
        for category, entries in self.weapons.items():
            for name, data in entries.items():
                yield DatabaseEntry(category=category, name=name, data=data)
        for category, entries in self.upgrades.items():
            for name, data in entries.items():
                yield DatabaseEntry(category=category, name=name, data=data)

    @classmethod
    def _apply_attribute(cls, item: DatabaseItem, attribute: str | None) -> object | None:
        if attribute is None:
            return item
        return cls._extract_attribute(item, attribute)

    @staticmethod
    def _extract_attribute(item: DatabaseItem, attribute: str) -> object | None:
        key = normalize_identifier(attribute)

        if key == "name":
            return item.data.context.get("name")

        if isinstance(item, Upgrade):
            if key in item.data.context:
                return item.data.context.get(key)
            if key in item.data.stats:
                return item.data.stats.get(key)
            return None

        if key in item.data.context:
            return item.data.context.get(key)

        calculator = item.stats
        for state_name in ("base", "effective"):
            state = getattr(calculator, state_name, None)
            if state is not None and key in state:
                return state.get(key)

        if key in item.data.stats:
            return item.data.stats.get(key)
        if hasattr(calculator, key):
            return getattr(calculator, key)
        if hasattr(item, key):
            return getattr(item, key)
        return None


arsenal = WarframeDatabase.from_files()
