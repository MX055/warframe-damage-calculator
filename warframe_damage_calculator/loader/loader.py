from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Literal, Self, overload

from ..models.melee import Melee
from ..models.primary import Primary
from ..models.secondary import Secondary
from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from .bundled_names import MeleeName, PrimaryName, SecondaryName, UpgradeName
from .construction import DatabaseFactory
from .matching import entry_matches
from .normalization import normalize_identifier, normalize_name
from .paths import DEFAULT_DATABASE_PATH, load_json
from .schema import DatabaseEntry

type DatabaseItem = Weapon | Upgrade
type WeaponItem = Primary | Secondary | Melee


class WarframeDatabase:
    def __init__(self, database: Mapping[str, Any]) -> None:
        self.database = database
        self.weapons = database.get("weapons", {})
        self.upgrades = database.get("upgrades", {})
        self.riven_stats = database.get("riven_stats", {})
        self._factory = DatabaseFactory()
        self._entries = tuple(self._iter_entries())
        self._name_index = {normalize_name(entry.name): entry for entry in self._entries}

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_DATABASE_PATH) -> Self:
        return cls(load_json(path))

    @classmethod
    def from_folder(cls, folder: str | Path) -> Self:
        return cls.from_file(Path(folder) / "database.json")

    @overload
    def get(self, name: PrimaryName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Primary: ...

    @overload
    def get(self, name: SecondaryName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Secondary: ...

    @overload
    def get(self, name: MeleeName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Melee: ...

    @overload
    def get(self, name: UpgradeName, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> Upgrade: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: None = ...) -> DatabaseItem | None: ...

    @overload
    def get(self, name: str, *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str) -> object | None: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: Literal["name"]) -> list[str]: ...

    @overload
    def get(self, name: None = ..., *, type: str | None = ..., context: Mapping[str, Any] | None = ..., attribute: str | None = ...) -> dict[str, DatabaseItem | object | None]: ...

    def get(
        self,
        name: str | None = None,
        *,
        type: str | None = None,
        context: Mapping[str, Any] | None = None,
        attribute: str | None = None,
    ) -> DatabaseItem | object | None:
        if name is not None:
            entry = self._name_index.get(normalize_name(name))
            if entry is None or not entry_matches(entry, type):
                return None
            return self._attribute(self._create(entry, context), attribute)

        entries = sorted(
            (entry for entry in self._entries if entry_matches(entry, type)),
            key=lambda entry: normalize_name(entry.name),
        )
        if attribute is not None and normalize_identifier(attribute) == "name":
            return [entry.name for entry in entries]
        return {entry.name: self._attribute(self._create(entry, context), attribute) for entry in entries}

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

    @staticmethod
    def _attribute(item: DatabaseItem, attribute: str | None) -> object:
        if attribute is None:
            return item
        key = normalize_identifier(attribute)
        if key == "name":
            return item.data.name
        contexts = (item.data.runtime, item.data.stats) if isinstance(item, Upgrade) else (item.data, item.data.ammo)
        for data in contexts:
            if key in data:
                return data[key]
        if isinstance(item, Weapon):
            selected = item.stats.attacks[item.stats._attack_name()]
            for state in (selected.base, selected.effective):
                if key in state:
                    return state[key]
            if key in item._attack:
                return item._attack[key]
            if key in item._attack.stats:
                return item._attack.stats[key]
        return None


arsenal = WarframeDatabase.from_file()
