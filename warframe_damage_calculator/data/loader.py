from pathlib import Path
from collections.abc import Iterator, Mapping
from copy import deepcopy
from typing import Any, Literal, overload, Self

from ..models.data import Data
from ..models.melee import Melee
from ..models.primary import Primary
from ..models.secondary import Secondary
from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from .bundled_names import MeleeName, PrimaryName, SecondaryName, UpgradeName
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


def _normalize_rank_locked_effect(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_rank_locked_effect(item) for item in value]
    if not isinstance(value, Mapping):
        return value

    normalized = {key: _normalize_rank_locked_effect(item) for key, item in value.items()}
    condition = normalized.get("when")
    if isinstance(condition, Mapping) and set(condition) == {"rank"}:
        normalized["at_rank"] = condition["rank"]
        del normalized["when"]
    return normalized


def _normalize_upgrades(upgrades: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(upgrades)
    for entries in normalized.values():
        for upgrade in entries.values():
            stats = upgrade.get("stats", {})
            for stat, effects in stats.items():
                stats[stat] = _normalize_rank_locked_effect(effects)
    return normalized


class WarframeDatabase:
    def __init__(self, weapons: Mapping[str, Any], upgrades: Mapping[str, Any]) -> None:
        self.weapons = weapons
        self.upgrades = _normalize_upgrades(upgrades)
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
    def get(self, name: str, *, type: WeaponFilter, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> WeaponItem | None: ...

    @overload
    def get(self, name: str, *, type: UpgradeFilter, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Upgrade | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> DatabaseItem | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> object | None: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: Literal["name"]) -> list[str]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> list[str] | dict[str, object | None]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> dict[str, DatabaseItem]: ...

    def get(self, name: str | None = None, *, type: str | None = None, context: Mapping[str, Any] | None = None, attribute: str | None = None) -> DatabaseItem | None | list[str] | dict[str, DatabaseItem] | dict[str, object | None]:
        if name is not None:
            entry = self._name_index.get(normalize_name(name))
            if entry is None or not entry_matches(entry, type):
                return None
            return self._apply_attribute(self._create(entry, context), attribute)

        entries = sorted((entry for entry in self._entries if entry_matches(entry, type)), key=lambda entry: normalize_name(entry.name))

        if attribute is not None and normalize_identifier(attribute) == "name":
            return [entry.name for entry in entries]

        return {entry.name: self._apply_attribute(self._create(entry, context), attribute) for entry in entries}

    def _create(self, entry: DatabaseEntry, context: Mapping[str, Any] | None) -> DatabaseItem:
        data = deepcopy(entry.data)
        data["context"] = dict(data.get("context", {})) | dict(context or {})
        return self._factory.create(DatabaseEntry(entry.category, entry.name, data))

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
    def _data_value(data: Data, key: str) -> tuple[bool, object | None]:
        try:
            return True, data[key]
        except KeyError:
            return False, None

    @staticmethod
    def _extract_attribute(item: DatabaseItem, attribute: str) -> object | None:
        key = normalize_identifier(attribute)

        if key == "name":
            return item.data.context.get("name")

        if isinstance(item, Upgrade):
            found, value = WarframeDatabase._data_value(item.data.context, key)
            if found:
                return value
            found, value = WarframeDatabase._data_value(item.data.stats, key)
            if found:
                return value
            return None

        found, value = WarframeDatabase._data_value(item.data.context, key)
        if found:
            return value

        calculator = item.stats
        for state_name in ("base", "effective"):
            state = getattr(calculator, state_name, None)
            if isinstance(state, Data):
                found, value = WarframeDatabase._data_value(state, key)
                if found:
                    return value

        found, value = WarframeDatabase._data_value(item.data.stats, key)
        if found:
            return value
        if hasattr(calculator, key):
            return getattr(calculator, key)
        if hasattr(item, key):
            return getattr(item, key)
        return None

class _BundledDatabase(WarframeDatabase):
    @overload
    def get(self, name: PrimaryName, *, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Primary: ...

    @overload
    def get(self, name: SecondaryName, *, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Secondary: ...

    @overload
    def get(self, name: MeleeName, *, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Melee: ...

    @overload
    def get(self, name: UpgradeName, *, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Upgrade: ...

    @overload
    def get(self, name: str, *, type: WeaponFilter, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> WeaponItem | None: ...

    @overload
    def get(self, name: str, *, type: UpgradeFilter, context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Upgrade | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> DatabaseItem | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> object | None: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: Literal["name"]) -> list[str]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> list[str] | dict[str, object | None]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> dict[str, DatabaseItem]: ...

    def get(self, name: str | None = None, *, type: str | None = None, context: Mapping[str, Any] | None = None, attribute: str | None = None) -> DatabaseItem | None | list[str] | dict[str, DatabaseItem] | dict[str, object | None]:
        return super().get(name, type=type, context=context, attribute=attribute)


arsenal = _BundledDatabase.from_files()
