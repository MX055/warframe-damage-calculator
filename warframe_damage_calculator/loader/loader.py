from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, Literal, Self, overload

from ..models.melee import Melee
from ..models.enemy import Enemy
from ..models.primary import Primary
from ..models.secondary import Secondary
from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from .bundled_names import EnemyName, MeleeName, PrimaryName, SecondaryName, UpgradeName
from .construction import DatabaseFactory
from .matching import entry_matches, normalize_filter
from .normalization import normalize_identifier, normalize_name
from .paths import load_bundled_database, load_json
from .schema import DatabaseEntry

type DatabaseItem = Weapon | Upgrade | Enemy
type WeaponItem = Primary | Secondary | Melee
_UPGRADE_FILTERS = frozenset({"upgrade", "mod", "arcane"})


class WarframeDatabase:
    def __init__(self, database: Mapping[str, Any]) -> None:
        self.database = database
        self.weapons = database.get("weapons", {})
        self.upgrades = database.get("upgrades", {})
        self.enemies = database.get("enemies", {})
        self.riven_stats = database.get("riven_stats", {})
        self._factory = DatabaseFactory()
        self._entries = tuple(self._iter_entries())
        name_index: dict[str, list[DatabaseEntry]] = {}
        for entry in self._entries:
            name_index.setdefault(normalize_name(entry.name), []).append(entry)
        self._name_index = {key: tuple(entries) for key, entries in name_index.items()}

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        return cls(load_json(path))

    @classmethod
    def from_folder(cls, folder: str | Path) -> Self:
        return cls.from_file(Path(folder) / "database.json")

    @classmethod
    def from_bundled(cls) -> Self:
        return cls(load_bundled_database())

    @overload
    def get(self, name: PrimaryName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Primary: ...

    @overload
    def get(self, name: SecondaryName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Secondary: ...

    @overload
    def get(self, name: MeleeName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Melee: ...

    @overload
    def get(self, name: UpgradeName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Upgrade: ...

    @overload
    def get(self, name: EnemyName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Enemy: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> DatabaseItem | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> object | None: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: Literal["name"]) -> list[str]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str | None = ...) -> dict[str, DatabaseItem | object | None]: ...

    def get(self, name: str | None = None, *, type: str | None = None, context: Mapping[str, Any] | None = None, attribute: str | None = None) -> DatabaseItem | object | None:
        if name is not None:
            entry = self._select_named_entry(self._name_index.get(normalize_name(name), ()), type)
            if entry is None:
                return None
            return self._attribute(self._create(entry, context), attribute)

        entries = sorted(
            (entry for entry in self._entries if entry_matches(entry, type)),
            key=lambda entry: normalize_name(entry.name),
        )
        if attribute is not None and normalize_identifier(attribute) == "name":
            return [entry.name for entry in entries]
        return {entry.name: self._attribute(self._create(entry, context), attribute) for entry in entries}

    @staticmethod
    def _select_named_entry(entries: tuple[DatabaseEntry, ...], item_type: str | None) -> DatabaseEntry | None:
        """Pick among same-named database entries using the type filter."""
        matched = [entry for entry in entries if entry_matches(entry, item_type)]
        if not matched:
            return None
        if len(matched) == 1:
            return matched[0]
        normalized = normalize_filter(item_type)
        if normalized == "enemy":
            for entry in matched:
                if entry.is_enemy:
                    return entry
        if normalized in _UPGRADE_FILTERS:
            for entry in matched:
                if entry.is_upgrade:
                    return entry
        for entry in matched:
            if entry.is_weapon:
                return entry
        for entry in matched:
            if entry.is_enemy:
                return entry
        return matched[0]

    def _create(self, entry: DatabaseEntry, context: Mapping[str, Any] | None) -> DatabaseItem:
        return self._factory.create(entry, dict(context or {}))

    def _iter_entries(self) -> Iterator[DatabaseEntry]:
        for raw in self.weapons.values():
            database_category = normalize_identifier(raw.get("type"))
            category = "primary" if database_category == "archgun" else database_category
            if category in {"primary", "secondary", "melee"}:
                yield DatabaseEntry(category, raw)

        for raw in self.upgrades.values():
            category = normalize_identifier(raw.get("type"))
            if category in {"mod", "arcane"}:
                compatibility = raw.get("compatibility", {})
                match_types = {normalize_identifier(item) for item in compatibility.get("types", [])}
                subtypes = {normalize_identifier(item) for item in compatibility.get("subtypes", [])}
                names = {normalize_name(item) for item in compatibility.get("names", [])}
                for weapon in self.weapons.values():
                    if normalize_identifier(weapon.get("subtype")) in subtypes or normalize_name(weapon.get("name")) in names:
                        match_types.add("primary" if weapon.get("type") == "archgun" else normalize_identifier(weapon.get("type")))
                yield DatabaseEntry(category, raw, match_types)

        for identifier, raw in self.enemies.items():
            yield DatabaseEntry("enemy", raw, identifier=identifier)

    @staticmethod
    def _attribute(item: DatabaseItem, attribute: str | None) -> object:
        if attribute is None:
            return item
        key = normalize_identifier(attribute)
        if key == "name":
            return item.data.name
        contexts = (item.data.runtime, item.data.stats) if isinstance(item, Upgrade) else (item.data, item.data.stats, item.data.modifiers, item.data.bodyparts) if isinstance(item, Enemy) else (item.data.runtime, item.data, item.data.ammo)
        for data in contexts:
            if key in data:
                return data[key]
        if isinstance(item, Weapon):
            selected = item.results.main
            for state in (selected.base, selected.effective):
                if key in state:
                    return state[key]
            attack = item.data.attacks[item.data.selected_attack]
            if key in attack:
                return attack[key]
            if key in attack.stats:
                return attack.stats[key]
        return None


class LazyWarframeDatabase:
    """Deferred bundled-database accessor; loads once on first use."""

    def __init__(self, factory: Callable[[], WarframeDatabase]) -> None:
        self._factory = factory
        self._database: WarframeDatabase | None = None

    def _resolve(self) -> WarframeDatabase:
        if self._database is None:
            self._database = self._factory()
        return self._database

    @property
    def database(self) -> Mapping[str, Any]:
        return self._resolve().database

    @property
    def weapons(self) -> Mapping[str, Any]:
        return self._resolve().weapons

    @property
    def upgrades(self) -> Mapping[str, Any]:
        return self._resolve().upgrades

    @property
    def enemies(self) -> Mapping[str, Any]:
        return self._resolve().enemies

    @property
    def riven_stats(self) -> Mapping[str, Any]:
        return self._resolve().riven_stats

    @overload
    def get(self, name: PrimaryName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Primary: ...

    @overload
    def get(self, name: SecondaryName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Secondary: ...

    @overload
    def get(self, name: MeleeName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Melee: ...

    @overload
    def get(self, name: UpgradeName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Upgrade: ...

    @overload
    def get(self, name: EnemyName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Enemy: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> DatabaseItem | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> object | None: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: Literal["name"]) -> list[str]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str | None = ...) -> dict[str, DatabaseItem | object | None]: ...

    def get(self, name: str | None = None, *, type: str | None = None, context: Mapping[str, Any] | None = None, attribute: str | None = None) -> DatabaseItem | object | None:
        return self._resolve().get(name, type=type, context=context, attribute=attribute)


arsenal = LazyWarframeDatabase(WarframeDatabase.from_bundled)
